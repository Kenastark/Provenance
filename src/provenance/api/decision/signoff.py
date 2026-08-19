"""Operator sign-off records — who authorised a dispatch, and proof of what they saw.

A sign-off is single-purpose: it names one event and one channel, records the
operator, hashes the exact evidence bundle they were shown, pins the model version
that produced the call, and expires. The gate will not deliver without one that is
valid for the event/channel at hand, not revoked, and not past its expiry — so a
stale token can never authorise a fresh alert.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.decision.channels import CHANNELS
from provenance.io.db import models as m

# Default validity window for a sign-off. A modelling choice, not a data constant: an
# operator's authorisation is a fresh decision, not a standing one.
DEFAULT_TTL_SECONDS = 900


class SignoffInvalid(Exception):
    """Raised when a sign-off is missing, mismatched, revoked, or expired."""


def evidence_hash(evidence: dict[str, Any]) -> str:
    """A stable digest of the evidence the operator saw, for tamper-evidence."""
    canonical = json.dumps(evidence, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def create_signoff(
    session: AsyncSession,
    *,
    event_id: int,
    channel: str,
    operator: str,
    evidence: dict[str, Any],
    model_version: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> m.SignoffToken:
    """Record an operator's sign-off and return the token that authorises a dispatch."""
    if channel not in CHANNELS:
        raise SignoffInvalid(f"Unknown channel {channel!r}; expected one of {sorted(CHANNELS)}.")
    now = now or datetime.now(UTC).replace(tzinfo=None)
    token = m.SignoffToken(
        id=f"so_{uuid.uuid4().hex}",
        event_id=event_id,
        channel=channel,
        operator=operator,
        evidence_hash=evidence_hash(evidence),
        evidence=evidence,
        model_version=model_version,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
        revoked=False,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def validate_signoff(
    session: AsyncSession,
    signoff_id: str,
    *,
    event_id: int,
    channel: str,
    now: datetime | None = None,
) -> m.SignoffToken:
    """Return the token iff it authorises *this* event/channel right now, else raise.

    This is the predicate the gate must call before any delivery. It is intentionally
    strict: a token for another event or channel, a revoked token, or an expired token
    is not merely ignored — it raises, so a caller cannot accidentally proceed on a
    falsy return.
    """
    now = now or datetime.now(UTC).replace(tzinfo=None)
    token = await session.get(m.SignoffToken, signoff_id)
    if token is None:
        raise SignoffInvalid(f"No sign-off {signoff_id!r} exists; a dispatch requires one.")
    if token.event_id != event_id or token.channel != channel:
        raise SignoffInvalid(
            f"Sign-off {signoff_id!r} authorises event {token.event_id}/{token.channel}, "
            f"not event {event_id}/{channel}."
        )
    if token.revoked:
        raise SignoffInvalid(f"Sign-off {signoff_id!r} was revoked.")
    if token.expires_at <= now:
        raise SignoffInvalid(f"Sign-off {signoff_id!r} expired at {token.expires_at.isoformat()}.")
    return token
