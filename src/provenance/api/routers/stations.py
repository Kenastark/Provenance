"""Station endpoints. Public: the network's stations and their coverage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.errors import ProblemException
from provenance.api.pagination import Page, clamp_limit, decode_cursor, encode_cursor
from provenance.api.schemas import StationOut
from provenance.io.db import models as m
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/stations", tags=["stations"])


def _to_out(s: m.Station) -> StationOut:
    return StationOut(
        station_id=s.station_id,
        name=s.name,
        lat=s.lat,
        lon=s.lon,
        zone_type=s.zone_type,
        coverage=dict(s.coverage or {}),
    )


@router.get("", response_model=Page[StationOut])
async def list_stations(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> Page[StationOut]:
    n = clamp_limit(limit)
    after = decode_cursor(cursor)
    rows = await repo.list_stations(session, limit=n + 1, after=after)
    items = [_to_out(s) for s in rows[:n]]
    next_cursor = encode_cursor(rows[n - 1].station_id) if len(rows) > n else None
    return Page(items=items, next_cursor=next_cursor, count=len(items))


@router.get("/{station_id}", response_model=StationOut)
async def get_station(
    station_id: str,
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> StationOut:
    station = await repo.get_station(session, station_id)
    if station is None:
        raise ProblemException(404, f"No station with id {station_id!r}.")
    return _to_out(station)
