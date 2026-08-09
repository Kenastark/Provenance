"""operational tables: maintenance queue, sign-off, dispatch (phase 7)

Revision ID: 0003_operational
Revises: 0002_residuals
Create Date: 2026-08-09

The phase-7 operational tables — ``maintenance_items``, ``maintenance_transitions``,
``signoff_tokens`` and ``dispatches`` — are plain relational tables (small, mutable
workflow state), not hypertables. On a fresh upgrade 0001's ``create_all`` already
reflects the current ORM metadata and makes them; this migration exists so a database
that predates phase 7 gains them too. Idempotent (``checkfirst``), and identical on
SQLite and Postgres because none of these tables need a Timescale-specific step.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from provenance.io.db.base import Base

revision: str = "0003_operational"
down_revision: str | None = "0002_residuals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "maintenance_items",
    "maintenance_transitions",
    "signoff_tokens",
    "dispatches",
)


def upgrade() -> None:
    bind = op.get_bind()
    # Create in dependency order (parents before children); create_all sorts by FK, so
    # passing the tables together is enough. checkfirst makes a fresh upgrade a no-op.
    Base.metadata.create_all(
        bind, tables=[Base.metadata.tables[name] for name in _TABLES], checkfirst=True
    )


def downgrade() -> None:
    for name in reversed(_TABLES):
        op.drop_table(name)
