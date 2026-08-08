"""Events endpoint. Public: candidate notable events.

The ``verdict`` field is present in the contract now but is null until Phase 4's
graph adjudicator fills it — the schema does not change when adjudication lands,
only the value does.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import EventOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/events", tags=["events"])


def _to_out(e: m.Event) -> EventOut:
    return EventOut(
        id=e.id,
        audit_run_id=e.audit_run_id,
        rank=e.rank,
        category=e.category,
        reason_code=e.reason_code,
        station_id=e.station_id,
        parameter=e.parameter,
        timestamp_utc=e.timestamp_utc.isoformat(),
        headline=e.headline,
        severity=e.severity,
        evidence=dict(e.evidence or {}),
        verdict=e.verdict,
    )


@router.get("", response_model=Page[EventOut])
async def list_events(
    station: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> Page[EventOut]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await repo.list_events(
        session, limit=n + 1, after=int(after) if after is not None else None, station_id=station
    )
    items = [_to_out(e) for e in rows[:n]]
    next_cursor = encode_cursor(rows[n - 1].id) if len(rows) > n else None
    return Page(items=items, next_cursor=next_cursor, count=len(items))
