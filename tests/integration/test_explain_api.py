"""The /v1/explain/{defect_id} endpoint: model-backed, rule, and degraded paths."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from provenance.api.app import create_app
from provenance.config.settings import get_settings
from provenance.io.db.engine import make_engine
from provenance.models import registry

pytestmark = pytest.mark.integration

RESEARCHER = {"X-API-Key": "prov-researcher-key"}


@pytest.fixture
def saved_models(trained_models: dict[str, object], tmp_path: Path) -> Path:
    art = tmp_path / "art"
    registry.save_model(trained_models["deweather"], artefacts_dir=art, docs_dir=tmp_path / "docs")  # type: ignore[arg-type]
    registry.save_model(trained_models["fault"], artefacts_dir=art, docs_dir=tmp_path / "docs")  # type: ignore[arg-type]
    return art


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


async def _first_r07_defect(client: httpx.AsyncClient) -> int:
    body = (await client.get("/v1/defects", params={"code": "R07"}, headers=RESEARCHER)).json()
    return int(body["items"][0]["id"])


async def test_explain_is_model_backed_when_artefacts_present(
    loaded_db: dict[str, str], saved_models: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(saved_models))
    get_settings.cache_clear()
    try:
        async with _client(loaded_db["url"]) as c:
            did = await _first_r07_defect(c)
            e = (await c.get(f"/v1/explain/{did}", headers=RESEARCHER)).json()
        assert e["method"] == "model"
        assert e["degraded"] is False
        assert e["attributions"], "a model-backed explanation must carry attributions"
        assert e["reconstructs"] is True
        # The impossible PM10 reading is classed by rule, not the ML (precedence).
        assert e["fault_class"] == "physically_impossible"
        assert "{" not in e["sentence"]
        assert e["model_versions"]
    finally:
        get_settings.cache_clear()


async def test_explain_degrades_without_artefacts(
    loaded_db: dict[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(tmp_path / "empty"))
    get_settings.cache_clear()
    try:
        async with _client(loaded_db["url"]) as c:
            did = await _first_r07_defect(c)
            e = (await c.get(f"/v1/explain/{did}", headers=RESEARCHER)).json()
        assert e["method"] == "degraded"
        assert e["degraded"] is True
        assert e["attributions"] == []
        assert "{" not in e["sentence"]  # the statistics-layer reason still renders
        assert any("statistics layer" in n for n in e["notes"])
    finally:
        get_settings.cache_clear()


async def test_explain_unknown_defect_is_404(loaded_db: dict[str, str]) -> None:
    async with _client(loaded_db["url"]) as c:
        resp = await c.get("/v1/explain/99999999", headers=RESEARCHER)
    assert resp.status_code == 404


async def test_explain_requires_researcher_role(loaded_db: dict[str, str]) -> None:
    async with _client(loaded_db["url"]) as c:
        resp = await c.get("/v1/explain/1", headers={"X-API-Key": "prov-public-key"})
    assert resp.status_code == 403
