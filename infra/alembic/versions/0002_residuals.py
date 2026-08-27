"""residuals: the deweathered residual series (phase 5)

Revision ID: 0002_residuals
Revises: 0001_initial
Create Date: 2026-08-09

The ``residuals`` table itself is created by 0001's ``Base.metadata.create_all``,
which reflects the current ORM metadata — so a fresh upgrade already has the table
by the time this migration runs. What is left here is the catch-up step for a
database migrated before this table existed: create it if it is not already there.
On a fresh upgrade that is a no-op, and the revision stays in the chain so the
history is linear on both paths.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from provenance.io.db.base import Base

revision: str = "0002_residuals"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent: on a DB migrated before this table existed, create it now; on a
    # fresh upgrade 0001 already made it, so create_all (checkfirst) is a no-op.
    Base.metadata.create_all(bind, tables=[Base.metadata.tables["residuals"]])


def downgrade() -> None:
    op.drop_table("residuals")
