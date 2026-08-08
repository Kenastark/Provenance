"""Defects endpoint. Researcher access: the flagged cells, filterable, paginated."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import DefectOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/defects", tags=["defects"])


def _to_out(d: m.Defect) -> DefectOut:
    return DefectOut(
        id=d.id,
        audit_run_id=d.audit_run_id,
        reason_code=d.reason_code,
        station_id=d.station_id,
        parameter=d.parameter,
        timestamp_utc=d.timestamp_utc.isoformat(),
        severity=d.severity,
        counts_toward_rate=d.counts_toward_rate,
        evidence=dict(d.evidence or {}),
    )


@router.get("", response_model=Page[DefectOut])
async def list_defects(
    code: str | None = Query(default=None),
    station: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> Page[DefectOut]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await repo.list_defects(
        session,
        limit=n + 1,
        after=int(after) if after is not None else None,
        code=code,
        station_id=station,
        severity=severity,
        start=start.replace(tzinfo=None) if start and start.tzinfo else start,
        end=end.replace(tzinfo=None) if end and end.tzinfo else end,
    )
    items = [_to_out(d) for d in rows[:n]]
    next_cursor = encode_cursor(rows[n - 1].id) if len(rows) > n else None
    return Page(items=items, next_cursor=next_cursor, count=len(items))
