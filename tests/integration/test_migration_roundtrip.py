"""Alembic up/down/up round trip on a real TimescaleDB container.

Marked ``needs_docker`` so it is excluded from the default gate; the stack must be
up and ``DATABASE_URL`` must point at Postgres. Proves the migration creates the
hypertables and the PostGIS geometry column, and that it reverses cleanly.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = [pytest.mark.needs_docker, pytest.mark.integration]

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://provenance:provenance@localhost:5432/provenance"
)


def _requires_postgres() -> None:
    if not _DB_URL.startswith("postgresql"):
        pytest.skip("migration round trip requires a Postgres DATABASE_URL")


def _alembic_config() -> object:
    os.environ["DATABASE_URL"] = _DB_URL
    from provenance.config.settings import get_settings

    get_settings.cache_clear()
    from provenance.io.db.migrate import _alembic_config

    return _alembic_config()


def test_up_down_up_round_trip() -> None:
    _requires_postgres()
    from alembic import command

    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = create_engine(_DB_URL.replace("+aiosqlite", ""))
    with engine.connect() as conn:
        hypertables = {
            r[0]
            for r in conn.execute(
                text("SELECT hypertable_name FROM timescaledb_information.hypertables")
            )
        }
        assert {"readings", "trust_scores"} <= hypertables
        geom = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='stations' AND column_name='geom'"
            )
        ).fetchone()
        assert geom is not None
    engine.dispose()
