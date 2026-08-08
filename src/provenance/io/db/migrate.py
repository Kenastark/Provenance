"""Schema management behind ``prov db``.

On PostgreSQL this drives Alembic (the migration carries the TimescaleDB/PostGIS
DDL). On SQLite — the fast test path — there are no migrations to run, so it builds
the schema straight from the ORM metadata. Both paths converge on the same logical
schema; only the Postgres-specific extras differ, and those are proven by the
Dockerised round-trip test.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from provenance.config.settings import REPO_ROOT, get_settings
from provenance.io.db.engine import create_all, drop_all, make_engine

if TYPE_CHECKING:
    from alembic.config import Config

    from provenance.io.db.loader import LoadReport


def _url(override: str | None) -> str:
    return override or get_settings().database_url


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _alembic_config() -> Config:
    from alembic.config import Config

    return Config(str(REPO_ROOT / "alembic.ini"))


def upgrade(url: str | None = None) -> None:
    """Bring the database schema up to head."""
    resolved = _url(url)
    if _is_sqlite(resolved):
        asyncio.run(_sqlite_create(resolved))
        return
    from alembic import command

    command.upgrade(_alembic_config(), "head")


def reset(url: str | None = None) -> None:
    """Drop everything and rebuild — destructive, for local resets only."""
    resolved = _url(url)
    if _is_sqlite(resolved):
        asyncio.run(_sqlite_reset(resolved))
        return
    from alembic import command

    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


async def _sqlite_create(url: str) -> None:
    engine = make_engine(url)
    try:
        await create_all(engine)
    finally:
        await engine.dispose()


async def _sqlite_reset(url: str) -> None:
    engine = make_engine(url)
    try:
        await drop_all(engine)
        await create_all(engine)
    finally:
        await engine.dispose()


def load(
    source: Path, *, url: str | None = None, source_name: str = "green_sentinel"
) -> LoadReport:
    """Load a data drop into the database, idempotently. Returns the LoadReport."""
    from provenance.io.db.engine import make_engine as _mk
    from provenance.io.db.engine import make_sessionmaker
    from provenance.io.db.loader import load_path

    async def _run() -> LoadReport:
        engine = _mk(_url(url))
        sm = make_sessionmaker(engine)
        try:
            async with sm() as session:
                return await load_path(session, Path(source), source=source_name)
        finally:
            await engine.dispose()

    return asyncio.run(_run())
