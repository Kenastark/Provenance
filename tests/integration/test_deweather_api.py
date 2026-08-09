"""The /v1/deweather/{station} endpoint: the before/after series, or an honest degraded state."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from provenance.api.app import create_app
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.models.deweather import store_residuals

pytestmark = pytest.mark.integration

PUBLIC = {"X-API-Key": "prov-public-key"}


@asynccontextmanager
async def _client(url: str) -> AsyncIterator[httpx.AsyncClient]:
    engine = make_engine(url)
    app = create_app(engine=engine)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield client
    finally:
        await engine.dispose()


async def test_deweather_series_served_when_residuals_stored(
    trained_models: dict[str, object], tmp_path: object
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path}/dw.db"  # type: ignore[str-bytes-safe]
    engine = make_engine(url)
    await create_all(engine)
    sm = make_sessionmaker(engine)
    async with sm() as session:
        await store_residuals(
            session,
            trained_models["deweather"],  # type: ignore[arg-type]
            trained_models["frame"],  # type: ignore[arg-type]
            weather=trained_models["weather"],  # type: ignore[arg-type]
        )
    await engine.dispose()

    async with _client(url) as c:
        body = (
            await c.get("/v1/deweather/STA-01", params={"parameter": "PM10"}, headers=PUBLIC)
        ).json()
    assert body["degraded"] is False
    assert body["series"], "a stored series must be returned"
    assert body["model_version"]
    point = body["series"][0]
    assert abs(point["residual"] - (point["actual"] - point["predicted"])) < 1e-6


async def test_deweather_degrades_without_residuals(api_client: httpx.AsyncClient) -> None:
    # The fixture DB has no residuals, so the endpoint returns an honest empty, degraded set.
    body = (
        await api_client.get("/v1/deweather/STA-01", params={"parameter": "PM10"}, headers=PUBLIC)
    ).json()
    assert body["degraded"] is True
    assert body["series"] == []
