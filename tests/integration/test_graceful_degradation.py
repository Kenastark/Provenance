"""Graceful degradation — the demo-day insurance policy (standing rule 6).

With every model artefact deleted, the API must still return trust scores from the
statistics layer, flagged degraded and complete with their component breakdown and
reason codes. This is marked demo_critical: if it ever fails, the fallback the whole
pitch leans on has broken.
"""

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

pytestmark = [pytest.mark.integration, pytest.mark.demo_critical]

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


async def test_trust_survives_deleting_every_model_artefact(
    loaded_db: dict[str, str],
    trained_models: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    art = tmp_path / "art"
    registry.save_model(trained_models["deweather"], artefacts_dir=art, docs_dir=tmp_path / "docs")  # type: ignore[arg-type]
    registry.save_model(trained_models["fault"], artefacts_dir=art, docs_dir=tmp_path / "docs")  # type: ignore[arg-type]
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(art))
    get_settings.cache_clear()
    try:
        async with _client(loaded_db["url"]) as c:
            # Models present: the score is not degraded.
            present = (await c.get("/v1/trust/STA-01", headers=PUBLIC)).json()
            assert present["degraded"] is False
            assert len(present["components"]) == 4

            # Delete every artefact — the insurance-policy scenario.
            for f in art.iterdir():
                f.unlink()

            degraded = (await c.get("/v1/trust/STA-01", headers=PUBLIC)).json()
        # Still a full trust score, now flagged degraded, from statistics alone.
        assert degraded["degraded"] is True
        assert len(degraded["components"]) == 4
        assert degraded["reason_codes"]
        assert any("statistics layer" in note for note in degraded["notes"])
    finally:
        get_settings.cache_clear()
