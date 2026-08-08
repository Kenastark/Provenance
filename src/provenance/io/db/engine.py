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
    """Create an async engine for ``url`` (defaults to the configured database)."""
    resolved = _async_url(url or get_settings().database_url)
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
