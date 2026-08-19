"""Async engine and session plumbing.

One factory builds an :class:`~sqlalchemy.ext.asyncio.AsyncEngine` from a URL; the
API and the loader share a sessionmaker bound to it. The default URL comes from
settings (TimescaleDB over psycopg); tests point it at ``sqlite+aiosqlite`` and
call :func:`create_all` instead of running migrations, which keeps the fast test
path free of Docker while the migration itself is proven separately.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from provenance.config.settings import get_settings
from provenance.io.db.base import Base


def _async_url(url: str) -> str:
    """Normalise a URL to an async driver.

    Accepts the settings default (already ``+psycopg``, which drives async too)
    and the bare ``sqlite://`` form used in tests, upgrading the latter to
    ``sqlite+aiosqlite``.
    """
    if url.startswith("sqlite") and "+aiosqlite" not in url:
        return url.replace("sqlite", "sqlite+aiosqlite", 1)
    return url


def make_engine(url: str | None = None) -> AsyncEngine:
    """Create an async engine for ``url`` (defaults to the configured database).

    SQLite (the test path, never production) picks the pool that keeps the database
    correct *and* leaves no aiosqlite worker thread alive between operations:

    * an in-memory database must reuse one connection (:class:`StaticPool`), or each new
      connection gets its own empty database;
    * a file-backed database uses :class:`NullPool`, which closes every connection on
      return, so no aiosqlite ``_connection_worker_thread`` outlives the fixture that
      opened it. A leftover worker thread racing the native math pools of a later
      torch-heavy test is the root cause of the macOS OpenMP segfault noted in
      ``tests/conftest.py`` (ADR 0009); disposing connections eagerly removes it at source.

    Production (psycopg/TimescaleDB) keeps the default pooled engine with pre-ping.
    """
    resolved = _async_url(url or get_settings().database_url)
    if resolved.startswith("sqlite"):
        if ":memory:" in resolved:
            return create_async_engine(
                resolved,
                future=True,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        # ``timeout`` makes a connection wait for a busy write lock rather than failing
        # immediately, so a concurrent dispatch reservation blocks and then resolves on
        # the unique constraint (a clean IntegrityError) instead of a raw "database is
        # locked" — which is what lets the idempotency-under-concurrency test be stable.
        return create_async_engine(
            resolved, future=True, poolclass=NullPool, connect_args={"timeout": 30}
        )
    return create_async_engine(resolved, future=True, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A sessionmaker that yields expire-on-commit-off sessions for request use."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def create_all(engine: AsyncEngine) -> None:
    """Create every table from the ORM metadata (test path; prod uses Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all(engine: AsyncEngine) -> None:
    """Drop every table from the ORM metadata (test/reset path)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
