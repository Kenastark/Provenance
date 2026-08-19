"""Residuals are stored in the database alongside the model version that made them (§7.6)."""

from __future__ import annotations

import pytest

from provenance.io.db import repository as repo
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.models.deweather import store_residuals

pytestmark = pytest.mark.integration


async def test_store_and_read_residuals(
    trained_models: dict[str, object], tmp_path: object
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path}/residuals.db"  # type: ignore[str-bytes-safe]
    engine = make_engine(url)
    await create_all(engine)
    sm = make_sessionmaker(engine)

    model = trained_models["deweather"]
    frame = trained_models["frame"]
    weather = trained_models["weather"]

    async with sm() as session:
        n = await store_residuals(session, model, frame, weather=weather)  # type: ignore[arg-type]
        assert n > 0

    async with sm() as session:
        rows = await repo.residuals_for_station(session, "STA-01", parameter="PM10")
        assert rows
        assert all(r.model_version == model.version for r in rows)  # type: ignore[attr-defined]
        # residual = actual - predicted, stored exactly.
        r = rows[0]
        assert abs(r.residual - (r.actual - r.predicted)) < 1e-6

    # Idempotent: re-storing the same model version overwrites rather than duplicates.
    async with sm() as session:
        n2 = await store_residuals(session, model, frame, weather=weather)  # type: ignore[arg-type]
        assert n2 == n
    async with sm() as session:
        again = await repo.residuals_for_station(session, "STA-01", parameter="PM10")
        assert len(again) == len(rows)
    await engine.dispose()
