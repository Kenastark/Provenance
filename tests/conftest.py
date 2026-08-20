"""Shared test fixtures.

Two rules this file enforces:

1. Determinism. Every test runs under a fixed seed, so a failure is reproducible
   from the test name alone.
2. No real data. Nothing here reads from data/raw. The test suite must pass on a
   fresh clone with an empty data directory, and CI checks that.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pandas as pd
import pytest
import pytest_asyncio
import torch

# Single-threaded native math pools, for two reasons. Primarily determinism: CPU results
# are only guaranteed byte-identical single-threaded (ADR 0009, standing rule 8), and these
# models are tiny so there is nothing to parallelise. Secondarily defense-in-depth: on
# macOS the several bundled OpenMP runtimes (torch, numba, sklearn, scipy) could race a
# stray aiosqlite worker thread and segfault a large `torch.tensor` build. That race's root
# cause — a worker thread outliving its fixture — is now fixed at source (file-backed test
# DBs use NullPool in `io/db/engine.make_engine`, so connections close eagerly); this keeps
# the belt alongside that fix. The env vars are read lazily by each runtime on first use
# (after this module loads); torch takes the immediate runtime setter. CI (Linux) unaffected.
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
torch.set_num_threads(1)

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
async def api_client(
    loaded_db: dict[str, str], tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[object]:
    """An httpx AsyncClient bound to the app over the loaded SQLite database.

    ``data_raw`` points at a freshly minted, permanently empty directory rather
    than the default ``data/raw`` — the reference endpoints (bus stops, traffic
    counters) read the filesystem directly, and this repo's real ``data/raw`` can
    carry the developer's actual drop. Without this override a passing test on one
    machine could fail on another's clean checkout (rule 7).
    """
    import httpx

    from provenance.api.app import create_app
    from provenance.io.db.engine import make_engine

    engine = make_engine(loaded_db["url"])
    empty_data_raw = tmp_path_factory.mktemp("data-raw-empty")
    app = create_app(engine=engine, data_raw=empty_data_raw)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await engine.dispose()


def _build_ops_db(db_path: Path) -> str:
    """Build a fresh SQLite DB with the fixture corpus loaded, exposure computed from a
    generated GTFS bundle, and events adjudicated — the full phase-7 operational state.

    Written to a directory so ``load_path`` discovers both the readings and the GTFS
    bundle exactly as the real product flow does, giving measured PopulationExposure
    and event verdicts the Alert Centre can rank.
    """
    from provenance.fixtures.generator import write_corpus
    from provenance.fixtures.gtfs import write_gtfs_bundle
    from provenance.graph.persist import adjudicate_stored_events
    from provenance.io import loaders
    from provenance.io.db.engine import create_all, make_engine, make_sessionmaker
    from provenance.io.db.loader import load_path

    drop = db_path.parent / "drop"
    write_corpus(drop, seed=SEED, n_days=14, n_stations=4)
    meta = loaders.load_station_metadata(drop)
    write_gtfs_bundle(drop, {sid: (loc.lat, loc.lon) for sid, loc in meta.items()})
    url = f"sqlite+aiosqlite:///{db_path}"

    async def _build() -> str:
        engine = make_engine(url)
        await create_all(engine)
        sm = make_sessionmaker(engine)
        async with sm() as session:
            report = await load_path(session, drop, source="fixtures")
            frame = loaders.load_data(drop)
            await adjudicate_stored_events(session, frame, dict(meta))
        await engine.dispose()
        return report.audit_run_id

    return asyncio.run(_build())


@pytest.fixture
def ops_db(tmp_path: Path) -> dict[str, str]:
    """A fresh, writable DB with full operational state, built synchronously.

    Function-scoped and isolated (its own SQLite file), because the operational tests
    mutate — they create sign-offs, dispatches, and maintenance transitions — and must
    not see or leave state for another test. Built in a sync fixture (like
    ``loaded_db``) so the ``asyncio.run`` inside does not collide with the running loop
    of an async test.
    """
    db_path = tmp_path / "ops.db"
    run_id = _build_ops_db(db_path)
    return {
        "url": f"sqlite+aiosqlite:///{db_path}",
        "run_id": run_id,
        "drop": str(db_path.parent / "drop"),
    }


@pytest_asyncio.fixture
async def ops_client(ops_db: dict[str, str]) -> AsyncIterator[object]:
    """An httpx client over the ``ops_db`` database.

    ``data_raw`` points at ``_build_ops_db``'s own drop directory, which already
    carries a real synthetic GTFS bundle (written by ``write_gtfs_bundle`` for the
    exposure factor) — reusing it means the reference bus-stops endpoint has real
    fixture data to serve rather than needing a third synthetic corpus.
    """
    import httpx

    from provenance.api.app import create_app
    from provenance.io.db.engine import make_engine

    engine = make_engine(ops_db["url"])
    app = create_app(engine=engine, data_raw=Path(ops_db["drop"]))
    app.state.run_id = ops_db["run_id"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await engine.dispose()


@pytest.fixture(scope="session")
def ops_db_shared(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A session-shared operational DB, built once, for read-mostly matrix checks.

    The RBAC matrix is 19 endpoints × 5 roles; rebuilding the DB per case would cost
    minutes. Auth outcomes do not depend on the additive writes those cases make, so a
    single shared database is safe here (and only the matrix uses it).
    """
    db_path = tmp_path_factory.mktemp("ops-shared") / "ops.db"
    run_id = _build_ops_db(db_path)
    return {
        "url": f"sqlite+aiosqlite:///{db_path}",
        "run_id": run_id,
        "drop": str(db_path.parent / "drop"),
    }


@pytest_asyncio.fixture
async def rbac_client(ops_db_shared: dict[str, str]) -> AsyncIterator[object]:
    """An httpx client over the session-shared operational DB (RBAC matrix only)."""
    import httpx

    from provenance.api.app import create_app
    from provenance.io.db.engine import make_engine

    engine = make_engine(ops_db_shared["url"])
    app = create_app(engine=engine, data_raw=Path(ops_db_shared["drop"]))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await engine.dispose()


@pytest.fixture(scope="session")
def demo_drop(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """A written corpus drop (readings + coordinates + GTFS) for the demo-mode tests.

    Session-scoped: built once, read many. Returns the loaded frame, the station
    metadata, and the drop path, so demo scenarios can be built in-memory (frame +
    meta) and the CLI can be pointed at the path.
    """
    from provenance.fixtures.generator import write_corpus
    from provenance.fixtures.gtfs import write_gtfs_bundle
    from provenance.io import loaders

    drop = tmp_path_factory.mktemp("demo-drop") / "corpus"
    write_corpus(drop, seed=SEED, n_days=14, n_stations=6)
    meta = loaders.load_station_metadata(drop)
    write_gtfs_bundle(drop, {sid: (loc.lat, loc.lon) for sid, loc in meta.items()})
    frame = loaders.load_data(drop)
    return {"path": drop, "frame": frame, "meta": dict(meta)}


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
