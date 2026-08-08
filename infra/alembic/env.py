"""Alembic environment.

The URL comes from settings (``DATABASE_URL``), coerced to a *sync* psycopg driver
because Alembic runs migrations synchronously. ``target_metadata`` is the ORM's
metadata so ``--autogenerate`` works, but the initial migration also carries the
TimescaleDB/PostGIS DDL that the ORM can't express.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from provenance.config.settings import get_settings
from provenance.io.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_url() -> str:
    url = get_settings().database_url
    # Alembic is synchronous; strip any async driver marker. psycopg3 drives both.
    return url.replace("+aiosqlite", "").replace("sqlite+aiosqlite", "sqlite")


config.set_main_option("sqlalchemy.url", _sync_url())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
