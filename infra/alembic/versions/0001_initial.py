"""initial schema: readings, audits, trust, coverage, ingest provenance

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08

The base tables are created from the ORM metadata so this migration cannot drift
from the models. On PostgreSQL it then layers on the parts the ORM can't
express: the PostGIS extension and a ``geometry(Point, 4326)`` column on
``stations``. On SQLite those extras are skipped, which is what lets the fast test
path build the same logical schema without Docker.
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

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Station geometry: the PostGIS point the ORM carries only as lat/lon floats.
    # A STORED generated column keeps geom in lock-step with lat/lon on every insert
    # and update, so populating coordinates is enough — there is no separate write
    # path that could leave geom stale. NULL coordinates yield a NULL point.
    op.execute(
        "ALTER TABLE stations ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326) "
        "GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE stations DROP COLUMN IF EXISTS geom")
    Base.metadata.drop_all(bind)
