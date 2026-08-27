"""Full-stack integration: migrate → load → audit → serve → hit every endpoint.

Marked ``needs_docker``: runs against the real Postgres from the compose stack
(``DATABASE_URL`` points at Postgres). This is the "is it a product?" test — the
same load and serve path the demo uses, end to end, on the real engine.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.needs_docker, pytest.mark.e2e]

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://provenance:provenance@localhost:5432/provenance"
)

_ENDPOINTS = [
    ("/healthz", None),
    ("/readyz", None),
    ("/version", None),
    ("/v1/stations", "public"),
    ("/v1/stations/STA-01", "public"),
    ("/v1/readings?limit=5", "researcher"),
    ("/v1/defects?limit=5", "researcher"),
    ("/v1/trust/STA-01", "public"),
    ("/v1/trust/STA-01?series=true", "public"),
    ("/v1/quality/summary", "public"),
    ("/v1/events?limit=5", "public"),
    ("/v1/audit/runs", "researcher"),
]

_KEYS = {"public": "prov-public-key", "researcher": "prov-researcher-key"}


def test_full_stack_load_and_serve() -> None:
    # A plain sync test: migrate.reset()/load() drive their own event loop, so the
    # serving half is run explicitly via asyncio.run to avoid a nested loop.
    if not _DB_URL.startswith("postgresql"):
        pytest.skip("stack integration requires a Postgres DATABASE_URL")
    os.environ["DATABASE_URL"] = _DB_URL
    from provenance.config.settings import get_settings

    get_settings.cache_clear()

    from provenance.io.db import migrate

    migrate.reset()
    report = migrate.load(Path("tests/fixtures"), source_name="fixtures")
    asyncio.run(_serve_and_check(report.audit_run_id))


async def _serve_and_check(run_id: str) -> None:
    from provenance.api.app import create_app
    from provenance.io.db.engine import make_engine

    engine = make_engine(_DB_URL)
    app = create_app(engine=engine)
    transport = httpx.ASGITransport(app=app)
    endpoints = [
        *_ENDPOINTS,
        (f"/v1/audit/runs/{run_id}", "researcher"),
        (f"/v1/export/audit-trail?format=csv&run_id={run_id}", "researcher"),
        (f"/v1/export/audit-trail?format=json&run_id={run_id}", "researcher"),
    ]
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for path, role in endpoints:
            headers = {"X-API-Key": _KEYS[role]} if role else {}
            resp = await client.get(path, headers=headers)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text[:200]}"

        # The trust guarantee holds end to end on the real engine.
        trust = (
            await client.get("/v1/trust/STA-01", headers={"X-API-Key": _KEYS["public"]})
        ).json()
        assert trust["components"] and trust["reason_codes"]

    await engine.dispose()
