"""The /v1/graph/attention endpoint: the HST-GAT's attention overlay, or an honest
degraded reason (standing rule 6)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from provenance.api.app import create_app
from provenance.config.settings import get_settings
from provenance.io.db.engine import make_engine

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


@pytest.fixture(scope="module")
def hstgat_db(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """A DB and a trained HST-GAT artefact built from the same drop, so the model's
    target parameter and station ids agree with what the endpoint reads back out.
    """
    from provenance.config.loading import load_graph_config, load_models_config
    from provenance.fixtures.generator import write_corpus
    from provenance.graph.build import station_points_from_metadata
    from provenance.graph.wind import WindField
    from provenance.io import loaders
    from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
    from provenance.io.db.loader import load_path
    from provenance.models.hstgat import store
    from provenance.models.hstgat.data import build_batch
    from provenance.models.hstgat.train import train_model

    root = tmp_path_factory.mktemp("hstgat")
    drop = root / "drop"
    write_corpus(drop, n_days=14, n_stations=4)
    meta = loaders.load_station_metadata(drop)
    frame = loaders.load_data(drop)
    points = station_points_from_metadata(dict(meta))
    gcfg = load_graph_config()

    batch = build_batch(frame, points, WindField.from_frame(frame), gcfg, target_parameter="PM10")
    trained = train_model(
        batch, kind="hstgat", cfg=load_models_config(), epochs=20, data_checksum="apitest01"
    )
    artefacts_dir = root / "artefacts"
    store.save_model(trained, artefacts_dir=artefacts_dir, docs_dir=root / "docs")

    db_path = root / "hstgat.db"
    url = f"sqlite+aiosqlite:///{db_path}"

    async def _build() -> None:
        engine = make_engine(url)
        await create_all(engine)
        sm = make_sessionmaker(engine)
        async with sm() as session:
            await load_path(session, drop, source="fixtures")
        await engine.dispose()

    asyncio.run(_build())
    return {"url": url, "artefacts_dir": artefacts_dir}


async def test_attention_overlay_degrades_when_no_artefact_is_trained(
    loaded_db: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(tmp_path / "empty"))
    get_settings.cache_clear()
    try:
        async with _client(loaded_db["url"]) as c:
            body = (await c.get("/v1/graph/attention", headers=PUBLIC)).json()
        assert body["available"] is False
        assert "has not been trained" in body["reason"]
        assert body["relations"] == {}
        assert body["at"] is None
    finally:
        get_settings.cache_clear()


async def test_attention_overlay_is_served_once_the_hstgat_is_trained(
    hstgat_db: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(hstgat_db["artefacts_dir"]))
    get_settings.cache_clear()
    try:
        async with _client(str(hstgat_db["url"])) as c:
            body = (await c.get("/v1/graph/attention", headers=PUBLIC)).json()
        assert body["available"] is True
        assert body["reason"] is None
        assert body["target_parameter"] == "PM10"
        assert body["at"] is not None
        assert body["relations"]  # at least one relation lit up
        for edges in body["relations"].values():
            for edge in edges:
                assert {"src", "dst", "attention", "edge_weight"} <= set(edge)
                assert 0.0 <= edge["attention"] <= 1.0
    finally:
        get_settings.cache_clear()
