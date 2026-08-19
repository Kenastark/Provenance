"""The human sign-off and dispatch surface (§2, §4). Operator access.

Two actions, in order. First an operator records a **sign-off** for a specific event
and channel: this captures who they are, the exact evidence they saw (hashed), and
the model version behind the call. Then a **dispatch** delivers the public alert —
but only through :func:`provenance.api.decision.gate.dispatch`, which refuses to send
without a valid sign-off and is idempotent on ``(event, channel, sign-off)``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.decision import gate, signoff
from provenance.api.decision.channels import CHANNELS
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.io.db import models as m

router = APIRouter(prefix="/v1/decision", tags=["decision"])


class SignoffIn(BaseModel):
    event_id: int
    channel: str = Field(description="webhook | email | sms.")
    operator: str = Field(default="operator", description="Who is signing off.")
    evidence: dict[str, Any] | None = Field(
        default=None, description="What the operator saw; defaults to the event's evidence."
    )
    model_version: str | None = Field(default=None)
    ttl_seconds: int = Field(default=signoff.DEFAULT_TTL_SECONDS, ge=1, le=86_400)


class DispatchIn(BaseModel):
    event_id: int
    channel: str
    signoff_id: str


async def _default_model_version() -> str:
    from provenance.api.models_status import model_versions

    versions = {"trust_score": "v1", **model_versions()}
    return ";".join(f"{k}={v}" for k, v in sorted(versions.items()))


async def _get_event(session: AsyncSession, event_id: int) -> m.Event:
    event = await session.get(m.Event, event_id)
    if event is None:
        raise ProblemException(404, f"No event {event_id}.")
    return event


@router.post("/signoff")
async def create_signoff(
    body: SignoffIn,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    if body.channel not in CHANNELS:
        raise ProblemException(
            422, f"Unknown channel {body.channel!r}; expected one of {sorted(CHANNELS)}."
        )
    event = await _get_event(session, body.event_id)
    evidence = body.evidence if body.evidence is not None else dict(event.evidence or {})
    model_version = body.model_version or await _default_model_version()
    try:
        token = await signoff.create_signoff(
            session,
            event_id=body.event_id,
            channel=body.channel,
            operator=body.operator,
            evidence=evidence,
            model_version=model_version,
            ttl_seconds=body.ttl_seconds,
        )
    except signoff.SignoffInvalid as exc:
        raise ProblemException(422, str(exc)) from exc
    return {
        "signoff_id": token.id,
        "event_id": token.event_id,
        "channel": token.channel,
        "operator": token.operator,
        "evidence_hash": token.evidence_hash,
        "model_version": token.model_version,
        "created_at": token.created_at.isoformat(),
        "expires_at": token.expires_at.isoformat(),
    }


@router.post("/dispatch")
async def dispatch_alert(
    body: DispatchIn,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.OPERATOR)),
) -> dict[str, Any]:
    event = await _get_event(session, body.event_id)
    try:
        result = await gate.dispatch(
            session,
            event_id=body.event_id,
            channel=body.channel,
            signoff_id=body.signoff_id,
            headline=event.headline,
        )
    except signoff.SignoffInvalid as exc:
        raise ProblemException(
            422, str(exc), type_="https://provenance.example/problems/signoff-required"
        ) from exc
    return result.to_dict()
