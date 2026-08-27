"""The declarative base and shared column conventions for the persistence layer.

Everything the product persists shares two provenance columns wherever it makes
sense: the ``ingest_batch_id`` that first brought a row into the system, and the
``audit_run_id`` that judged it. Provenance of the data is the product, so the
schema is built to answer "where did this row come from, and which run scored it?"
for every row it holds.

The ORM stays deliberately portable. Station location lives here as ``lat``/``lon``
floats so the whole model builds on SQLite for the fast test path; the PostGIS
``geometry(Point, 4326)`` column is added by the Alembic migration, which is
exercised by the Dockerised round-trip test.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for every persisted table."""
