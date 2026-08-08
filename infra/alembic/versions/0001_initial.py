"""initial schema: readings, audits, trust, coverage, ingest provenance

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08

The base tables are created from the ORM metadata so this migration cannot drift
from the models. On PostgreSQL it then layers on the parts the ORM can't express:
the TimescaleDB and PostGIS extensions, a ``geometry(Point, 4326)`` column on
``stations``, and the two hypertables (``readings`` and ``trust_scores``, chunked
by day). On SQLite those extras are skipped, which is what lets the fast test path
build the same logical schema without Docker.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from provenance.io.db.base import Base

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)

    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Station geometry: the PostGIS point the ORM carries only as lat/lon floats.
    op.execute("ALTER TABLE stations ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)")
    op.execute(
        "UPDATE stations SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326) "
        "WHERE lon IS NOT NULL AND lat IS NOT NULL"
    )

    # Hypertables. The partition column is part of each table's primary key, so
    # Timescale accepts them without dropping the key.
    op.execute(
        "SELECT create_hypertable('readings', 'timestamp_utc', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE, migrate_data => TRUE)"
    )
    op.execute(
        "SELECT create_hypertable('trust_scores', 'timestamp_utc', "
        "chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE, migrate_data => TRUE)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS geom")
    Base.metadata.drop_all(bind)
