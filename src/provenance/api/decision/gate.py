"""The dispatch gate: the one and only path from a decision to a public alert.

Two guarantees live here, and both are tested:

1. **Human sign-off (standing rule 5).** :func:`dispatch` calls
   :func:`~provenance.api.decision.signoff.validate_signoff` and will not reach the
   channel sender unless it returns a valid, non-expired token for this event and
   channel. ``tests/architecture/test_signoff_gate.py`` proves statically that the
   channel senders are unreachable except through this function, and that this
   function validates before it delivers.

2. **Idempotency (retries and concurrency).** The dispatch is keyed on
   ``(event_id, channel, signoff_id)``. The gate *reserves* that key with a unique
   database row **before** it sends, so a retry — or a second concurrent call — loses
   the reservation race, skips the send entirely, and returns the first result. A
   public alert is therefore delivered at most once per authorised decision.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.decision import channels
from provenance.api.decision.signoff import validate_signoff
from provenance.io.db import models as m


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """The outcome of a dispatch attempt, including whether it was an idempotent replay."""

    dispatch_id: str
    event_id: int
    channel: str
    signoff_id: str
    idempotency_key: str
    status: str
    idempotent: bool
    receipt: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "event_id": self.event_id,
            "channel": self.channel,
            "signoff_id": self.signoff_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "idempotent": self.idempotent,
            "receipt": self.receipt,
        }


def idempotency_key(event_id: int, channel: str, signoff_id: str) -> str:
    return f"{event_id}:{channel}:{signoff_id}"


def _result_from_row(row: m.Dispatch, *, idempotent: bool) -> DispatchResult:
    return DispatchResult(
        dispatch_id=row.id,
        event_id=row.event_id,
        channel=row.channel,
        signoff_id=row.signoff_id,
        idempotency_key=row.idempotency_key,
        status=row.status,
        idempotent=idempotent,
        receipt=(row.payload or {}).get("receipt"),
    )


async def _existing(session: AsyncSession, key: str) -> m.Dispatch | None:
    stmt = select(m.Dispatch).where(m.Dispatch.idempotency_key == key)
    return (await session.scalars(stmt)).first()


async def dispatch(
    session: AsyncSession,
    *,
    event_id: int,
    channel: str,
    signoff_id: str,
    headline: str = "",
    now: datetime | None = None,
) -> DispatchResult:
    """Deliver a public alert for ``event_id`` on ``channel`` under ``signoff_id``.

    Raises :class:`~provenance.api.decision.signoff.SignoffInvalid` when the sign-off
    does not authorise this dispatch. Returns an idempotent result (no second send)
    when the same key has already been dispatched. The send itself is
    :func:`channels.deliver` — called literally, and only here, so the static gate test
    can see that every delivery passes through this validated path.
    """
    key = idempotency_key(event_id, channel, signoff_id)
    now = now or datetime.now(UTC).replace(tzinfo=None)

    # Reserve the idempotency key with a unique row *before* sending (guarantee 2), and
    # validate the sign-off before doing so (guarantee 1). Under a concurrent retry the
    # loser's reservation collides on the unique constraint (or briefly blocks on the
    # write lock); it never sends, and returns the winner's result. A short bounded
    # loop turns a transient lock into that clean conflict rather than a hard failure.
    operator = model_version = evidence_hash = ""
    row: m.Dispatch | None = None
    for attempt in range(6):
        existing = await _existing(session, key)
        if existing is not None:
            return _result_from_row(existing, idempotent=True)
        if not operator:
            token = await validate_signoff(
                session, signoff_id, event_id=event_id, channel=channel, now=now
            )
            operator, model_version, evidence_hash = (
                token.operator,
                token.model_version,
                token.evidence_hash,
            )
        candidate = m.Dispatch(
            id=f"dsp_{uuid.uuid4().hex}",
            event_id=event_id,
            channel=channel,
            signoff_id=signoff_id,
            idempotency_key=key,
            status="pending",
            payload={},
            dispatched_at=now,
        )
        session.add(candidate)
        try:
            await session.flush()
            row = candidate
            break
        except IntegrityError:  # someone else reserved it first
            await session.rollback()
            continue
        except OperationalError:  # transient lock; back off and retry
            await session.rollback()
            await asyncio.sleep(0.02 * (attempt + 1))
            continue
    if row is None:
        winner = await _existing(session, key)
        if winner is not None:
            return _result_from_row(winner, idempotent=True)
        raise RuntimeError(f"Could not reserve dispatch for {key!r}.")

    # We own the reservation: this is the single delivery for this decision.
    payload = {
        "event_id": event_id,
        "channel": channel,
        "signoff_id": signoff_id,
        "idempotency_key": key,
        "operator": operator,
        "model_version": model_version,
        "evidence_hash": evidence_hash,
        "headline": headline,
    }
    receipt = channels.deliver(channel, payload)
    row.status = "sent"
    row.payload = {"request": payload, "receipt": receipt}
    await session.commit()
    await session.refresh(row)
    return _result_from_row(row, idempotent=False)
