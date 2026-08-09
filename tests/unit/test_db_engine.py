"""``make_engine`` pooling — correct for :memory:, and no aiosqlite thread outlives a fixture.

The macOS OpenMP segfault (phase-6 flag review) had a root cause: a file-backed test
database used a retaining pool (``AsyncAdaptedQueuePool``), so an aiosqlite
``_connection_worker_thread`` stayed alive in the pool and could race the native math
pools of a later torch-heavy test. The fix is to give file databases a ``NullPool`` that
closes every connection on return; an in-memory database keeps a ``StaticPool`` (one
reused connection) or its schema would vanish between connections.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.pool import NullPool, StaticPool

from provenance.io.db.engine import create_all, make_engine, make_sessionmaker


def test_file_sqlite_uses_nullpool_and_memory_uses_staticpool(tmp_path: Path) -> None:
    file_engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")
    mem_engine = make_engine("sqlite+aiosqlite:///:memory:")
    # File DB: NullPool closes each connection on return, so no worker thread lingers.
    # (Before the fix this was an AsyncAdaptedQueuePool, which retained the connection.)
    assert isinstance(file_engine.pool, NullPool)
    # :memory: must reuse one connection or each connection gets its own empty database.
    assert isinstance(mem_engine.pool, StaticPool)


def test_file_engine_leaves_no_worker_thread_even_without_dispose(tmp_path: Path) -> None:
    # Hold the engine (so GC cannot mask a leak) and deliberately skip dispose: a retaining
    # pool would leave the aiosqlite daemon worker thread alive; NullPool must not.
    baseline = threading.active_count()

    async def _op() -> object:
        engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'z.db'}")
        await create_all(engine)
        sm = make_sessionmaker(engine)
        async with sm() as session:
            await session.execute(text("select 1"))
        return engine  # not disposed on purpose

    engine = asyncio.run(_op())
    time.sleep(0.3)  # give any stray worker thread time to appear
    try:
        assert threading.active_count() <= baseline
    finally:
        asyncio.run(engine.dispose())  # type: ignore[attr-defined]
