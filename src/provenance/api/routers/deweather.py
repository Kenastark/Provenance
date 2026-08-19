"""Deweather endpoint: a station's raw vs weather-predicted vs residual series.

The before/after view the dashboard draws (§7.6). It serves the residuals stored by
``prov models residuals`` for one station and pollutant. When no residuals have been
stored — no model trained yet — it returns an empty series flagged ``degraded`` rather
than an error, so the chart shows an honest "train a model to see this" state instead
of breaking (standing rule 6).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.api.auth import Role
from provenance.api.deps import get_session, require
from provenance.api.schemas import DeweatherPointOut, DeweatherSeriesOut
from provenance.io.db import repository as repo

router = APIRouter(prefix="/v1/deweather", tags=["deweather"])


@router.get("/{station_id}", response_model=DeweatherSeriesOut)
async def get_deweather(
    station_id: str,
    parameter: str = Query(..., description="The pollutant to show the deweathered series for."),
    session: AsyncSession = Depends(get_session),
    _: Role = Depends(require(Role.PUBLIC_READ)),
) -> DeweatherSeriesOut:
    rows = await repo.residuals_for_station(session, station_id, parameter=parameter)
    if not rows:
        return DeweatherSeriesOut(station_id=station_id, parameter=parameter, degraded=True)
    return DeweatherSeriesOut(
        station_id=station_id,
        parameter=parameter,
        model_version=rows[0].model_version,
        degraded=False,
        series=[
            DeweatherPointOut(
                timestamp_utc=r.timestamp_utc.isoformat(),
                actual=r.actual,
                predicted=r.predicted,
                residual=r.residual,
            )
            for r in rows
        ],
    )
