"""Schemathesis property fuzz against the generated OpenAPI schema.

Every operation is exercised with generated inputs; the property asserted is the
one that matters for a public API — no input produces a server error. Client
errors (malformed cursors, bad filters) are expected and handled as RFC 7807
problems; a 5xx is a bug. The app is built once against a loaded SQLite database.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error

from provenance.api.app import create_app
from provenance.fixtures.generator import generate
from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
from provenance.io.db.loader import load_frame

pytestmark = pytest.mark.integration

_DB_FILE = Path(tempfile.mkdtemp(prefix="prov-st-")) / "schemathesis.db"
_URL = f"sqlite+aiosqlite:///{_DB_FILE}"


async def _build() -> None:
    engine = make_engine(_URL)
    await create_all(engine)
    sm = make_sessionmaker(engine)
    frame, _ = generate()
    async with sm() as session:
        await load_frame(session, frame, source="fixtures", path="tests/fixtures")
    await engine.dispose()


asyncio.run(_build())
_app = create_app(engine=make_engine(_URL))
# FastAPI emits OpenAPI 3.1, which schemathesis 3.x does not fully parse. Advertise
# 3.0.x for the fuzz only (this test-local app instance); production stays 3.1.
_app.openapi_version = "3.0.2"
_app.openapi_schema = None
schema = schemathesis.from_asgi("/openapi.json", _app)

_HEADERS = {"X-API-Key": "prov-operator-key"}


@pytest.mark.filterwarnings("ignore::ResourceWarning")
@schema.parametrize()
@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=list(HealthCheck),
)
def test_api_never_returns_a_server_error(case: schemathesis.Case) -> None:
    case.call_and_validate(checks=(not_a_server_error,), headers=_HEADERS)
