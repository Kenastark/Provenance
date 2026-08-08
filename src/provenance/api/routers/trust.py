"""Trust endpoint. Public: a station's trust score, always with its breakdown.

Point-in-time by default (the latest score); ``series=true`` returns the paginated
history. Both paths return :class:`TrustScoreOut`, whose ``components`` and
``reason_codes`` are required — there is no shape this endpoint can return that is
a bare number (standing rule 9).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import ComponentOut, RiskOut, TrustScoreOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/trust", tags=["trust"])


def _to_out(t: m.TrustScore) -> TrustScoreOut:
    return TrustScoreOut(
        station_id=t.station_id,
        timestamp_utc=t.timestamp_utc.isoformat(),
        trust=t.trust,
        components=[ComponentOut(**_component(c)) for c in t.components],
        reason_codes=list(t.reason_codes),
        risk=RiskOut(**t.risk),
        degraded=bool(t.degraded),
        notes=list(t.notes or []),
    )


def _component(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": c["name"],
        "value": c["value"],
        "weight": c["weight"],
        "contribution": c["contribution"],
        "is_placeholder": c.get("is_placeholder", False),
        "detail": c.get("detail", ""),
    }


@router.get("/{station_id}")
async def get_trust(
    station_id: str,
    series: bool = Query(
        default=False, description="Return the score history instead of the latest."
    ),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> TrustScoreOut | Page[TrustScoreOut]:
    if series or start or end:
        n = clamp_limit(limit)
        after = decode_cursor(cursor)
        rows = await repo.trust_series_for_station(
            session,
            station_id,
            limit=n + 1,
            after=str(after) if after is not None else None,
            start=start.replace(tzinfo=None) if start and start.tzinfo else start,
            end=end.replace(tzinfo=None) if end and end.tzinfo else end,
        )
        items = [_to_out(t) for t in rows[:n]]
        next_cursor = (
            encode_cursor(rows[n - 1].timestamp_utc.isoformat()) if len(rows) > n else None
        )
        return Page[TrustScoreOut](items=items, next_cursor=next_cursor, count=len(items))

    latest = await repo.latest_trust_for_station(session, station_id)
    if latest is None:
        raise ProblemException(
            404, f"No trust score for station {station_id!r}. Load a data drop first."
        )
    return _to_out(latest)
