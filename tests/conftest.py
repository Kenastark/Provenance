"""Shared test fixtures.

Two rules this file enforces:

1. Determinism. Every test runs under a fixed seed, so a failure is reproducible
   from the test name alone.
2. No real data. Nothing here reads from data/raw. The test suite must pass on a
   fresh clone with an empty data directory, and CI checks that.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pandas as pd
import pytest
import pytest_asyncio

SEED = 20260907


@pytest.fixture(autouse=True)
def _deterministic() -> Iterator[None]:
    """Reset RNG state before every test."""
    random.seed(SEED)
    try:
        import numpy as np

        np.random.seed(SEED)
    except ImportError:  # pragma: no cover - numpy is a hard dependency in practice
        pass
    yield


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """An isolated directory for tests that write files."""
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture
def synthetic_corpus() -> tuple[pd.DataFrame, object]:
    """The seeded synthetic corpus and its ground-truth ledger."""
    from provenance.fixtures.generator import generate

    return generate()


@pytest.fixture
def clean_corpus() -> pd.DataFrame:
    """A corpus with no injected defects - should trip no detector."""
    from provenance.fixtures.generator import generate

    frame, _ = generate(inject=False)
    return frame


@pytest.fixture
def make_ctx() -> Callable[[pd.DataFrame], object]:
    """Factory: build an AuditContext (real thresholds + coverage) for a frame."""
    from provenance.config.loading import load_thresholds
    from provenance.detectors.base import AuditContext
    from provenance.grid.coverage import build_coverage

    def _factory(frame: pd.DataFrame) -> AuditContext:
        return AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))

    return _factory


@pytest.fixture(scope="session")
def loaded_db(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A SQLite database file with the fixture corpus loaded once for the session.

    Built synchronously so it is available to both async API fixtures and the
    schemathesis module. Tests are read-only against it, so sharing is safe and
    avoids re-auditing per test.
    """
    from provenance.fixtures.generator import generate
    from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
    from provenance.io.db.loader import load_frame

    db_path = tmp_path_factory.mktemp("db") / "provenance.db"
    url = f"sqlite+aiosqlite:///{db_path}"

    async def _build() -> str:
        engine = make_engine(url)
        await create_all(engine)
        sm = make_sessionmaker(engine)
        frame, _ = generate()
        async with sm() as session:
            report = await load_frame(session, frame, source="fixtures", path="tests/fixtures")
        await engine.dispose()
        return report.audit_run_id

    run_id = asyncio.run(_build())
    return {"url": url, "run_id": run_id}


@pytest_asyncio.fixture
async def api_client(loaded_db: dict[str, str]) -> AsyncIterator[object]:
    """An httpx AsyncClient bound to the app over the loaded SQLite database."""
    import httpx

    from provenance.api.app import create_app
    from provenance.io.db.engine import make_engine

    engine = make_engine(loaded_db["url"])
    app = create_app(engine=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await engine.dispose()


@pytest.fixture(scope="session")
def weather_corpus() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A weather-coupled corpus + city weather frame, built once for the model tests."""
    from provenance.fixtures.weather import generate_weather_corpus

    return generate_weather_corpus(n_days=30, n_stations=6)


@pytest.fixture(scope="session")
def trained_models(weather_corpus: tuple[pd.DataFrame, pd.DataFrame]) -> dict[str, object]:
    """Deweather + fault models trained once and shared across the model test suite.

    Training the two LightGBM stacks is the slowest thing in the phase-5 tests, so it
    happens exactly once per session. Everything is deterministic (fixed seeds, single
    thread), so a shared model is byte-identical to one each test would build alone.
    """
    frame, weather = weather_corpus
    from provenance.models.deweather import train_deweather
    from provenance.models.fault import train_fault_classifier

    deweather = train_deweather(frame, weather=weather)
    fault = train_fault_classifier(frame, deweather, weather=weather)
    return {"frame": frame, "weather": weather, "deweather": deweather, "fault": fault}


@pytest.fixture
def make_frame() -> Callable[..., pd.DataFrame]:
    """Factory: build a small canonical long frame from simple per-series specs."""
    from provenance.schema import canonical as C

    def _factory(rows: list[dict]) -> pd.DataFrame:
        frame = pd.DataFrame(rows)
        if C.INSTRUMENT_ID not in frame.columns:
            frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
        if C.SOURCE_FILE not in frame.columns:
            frame[C.SOURCE_FILE] = "test_air.csv"
        frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
        frame = C.add_row_hash(frame)
        return C.validate(frame)

    return _factory
