"""Compute and persist the deweathered residual series.

The residual — actual minus weather-predicted — is stored with the ``model_version``
that produced it (§7.6). Storage is idempotent per ``(timestamp, station, parameter,
model_version)``: re-running the same model over the same data overwrites in place
rather than duplicating, so a residual row always reflects the latest run of a given
model version.

``models`` may import ``io`` (io is upstream); the reverse is forbidden, which is why
this persistence step lives here and not in the loader.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from provenance.io.db import models as m
from provenance.models.deweather.model import (
    ACTUAL,
    PREDICTED,
    RESIDUAL,
    DeweatherModel,
)
from provenance.schema import canonical as C


def residual_frame(
    model: DeweatherModel, frame: pd.DataFrame, *, weather: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Return the residual series for a readings frame under ``model``."""
    return model.predict_series(frame, weather=weather)


async def store_residuals(
    session: AsyncSession,
    model: DeweatherModel,
    frame: pd.DataFrame,
    *,
    weather: pd.DataFrame | None = None,
    audit_run_id: str | None = None,
) -> int:
    """Persist the residual series for ``frame`` under ``model``; return the row count."""
    residuals = residual_frame(model, frame, weather=weather)
    if residuals.empty:
        return 0

    # Idempotent: clear this model version's prior residuals before re-inserting.
    await session.execute(delete(m.Residual).where(m.Residual.model_version == model.version))

    rows = [
        {
            "timestamp_utc": pd.Timestamp(r[C.TIMESTAMP]).to_pydatetime(),
            "station_id": str(r[C.STATION_ID]),
            "parameter": str(r[C.PARAMETER]),
            "model_version": model.version,
            "actual": float(r[ACTUAL]),
            "predicted": float(r[PREDICTED]),
            "residual": float(r[RESIDUAL]),
            "audit_run_id": audit_run_id,
        }
        for r in residuals.to_dict(orient="records")
    ]
    session.add_all([m.Residual(**row) for row in rows])
    await session.commit()
    return len(rows)
