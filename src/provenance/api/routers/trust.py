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
from provenance.api.models_status import models_available
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import ComponentOut, RiskOut, TrustScoreOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/trust", tags=["trust"])

_DEGRADED_NOTE = (
    "Model artefacts are unavailable; this score comes from the statistics layer alone "
    "(graceful degradation, standing rule 6). Train models with `prov models train` to "
    "enrich it."
)


def _to_out(t: m.TrustScore, *, models_degraded: bool) -> TrustScoreOut:
    # A score is degraded if it was computed degraded OR the model layer is absent at
    # serving time. Either way the response says so — a trust layer never hides that it
    # is running on statistics alone.
    degraded = bool(t.degraded) or models_degraded
    notes = list(t.notes or [])
    if models_degraded and _DEGRADED_NOTE not in notes:
        notes.append(_DEGRADED_NOTE)
    return TrustScoreOut(
        station_id=t.station_id,
        timestamp_utc=t.timestamp_utc.isoformat(),
        trust=t.trust,
        components=[ComponentOut(**_component(c)) for c in t.components],
        reason_codes=list(t.reason_codes),
        risk=RiskOut(**t.risk),
        degraded=degraded,
        notes=notes,
        evidence=_evidence(t.components),
    )


def _evidence(components: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge the components' figures into one substitution map.

    Rows written before components carried evidence simply contribute nothing, so
    an older score still serialises - it just renders its sentences with an em dash
    where a number would go, exactly as it did before.
    """
    merged: dict[str, Any] = {}
    for component in components:
        merged.update(component.get("evidence") or {})
    return merged


def _component(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": c["name"],
        "value": c["value"],
        "weight": c["weight"],
        "contribution": c["contribution"],
        "is_placeholder": c.get("is_placeholder", False),
        "detail": c.get("detail", ""),
        "evidence": c.get("evidence") or {},
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
    models_degraded = not models_available()
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
        items = [_to_out(t, models_degraded=models_degraded) for t in rows[:n]]
        next_cursor = (
            encode_cursor(rows[n - 1].timestamp_utc.isoformat()) if len(rows) > n else None
        )
        return Page[TrustScoreOut](items=items, next_cursor=next_cursor, count=len(items))

    latest = await repo.latest_trust_for_station(session, station_id)
    if latest is None:
        raise ProblemException(
            404, f"No trust score for station {station_id!r}. Load a data drop first."
        )
    return _to_out(latest, models_degraded=models_degraded)
