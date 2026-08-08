"""Readings endpoint. Researcher access: raw or quality-flagged series, paginated.

``quality_flagged=true`` annotates each reading with the reason codes that fired on
its exact (station, parameter, timestamp) cell in the latest audit run, so a
researcher can pull the series already marked with what the audit found — the
difference between "the numbers" and "the numbers you can trust".
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import ReadingOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/readings", tags=["readings"])


def _to_out(r: m.Reading, flags: list[str] | None) -> ReadingOut:
    return ReadingOut(
        station_id=r.station_id,
        parameter=r.parameter,
        timestamp_utc=r.timestamp_utc.isoformat(),
        value=r.value,
        unit=r.unit,
        instrument_id=r.instrument_id,
        source_file=r.source_file,
        row_hash=r.row_hash,
        reason_codes=flags,
    )


@router.get("", response_model=Page[ReadingOut])
async def list_readings(
    request: Request,
    station: str | None = Query(default=None),
    parameter: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    quality_flagged: bool = Query(default=False, description="Annotate with audit reason codes."),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.RESEARCHER)),
) -> Page[ReadingOut]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await repo.list_readings(
        session,
        limit=n + 1,
        after=tuple(after) if after else None,
        station_id=station,
        parameter=parameter,
        start=_naive(start),
        end=_naive(end),
    )
    page_rows = rows[:n]
    flag_index: dict[tuple[str, str, datetime], list[str]] = {}
    if quality_flagged and page_rows:
        flag_index = await _flags_for(session, page_rows)
    items = [
        _to_out(
            r,
            flag_index.get((r.station_id, r.parameter, r.timestamp_utc), [])
            if quality_flagged
            else None,
        )
        for r in page_rows
    ]
    next_cursor = (
        encode_cursor([rows[n - 1].timestamp_utc.isoformat(), rows[n - 1].row_hash])
        if len(rows) > n
        else None
    )
    return Page(items=items, next_cursor=next_cursor, count=len(items))


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


async def _flags_for(
    session: AsyncSession, rows: Sequence[m.Reading]
) -> dict[tuple[str, str, datetime], list[str]]:
    latest = await repo.latest_audit_run(session)
    if latest is None:
        return {}
    stations = {r.station_id for r in rows}
    stmt = (
        select(m.Defect)
        .where(m.Defect.audit_run_id == latest.id)
        .where(m.Defect.station_id.in_(stations))
    )
    index: dict[tuple[str, str, datetime], list[str]] = {}
    for d in (await session.scalars(stmt)).all():
        index.setdefault((d.station_id, d.parameter, d.timestamp_utc), []).append(d.reason_code)
    return index
