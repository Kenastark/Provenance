"""The SQLite paths of schema management and the ``prov db`` CLI.

The Postgres/Alembic branch is proven by the Dockerised round-trip test; here the
SQLite branch (ORM ``create_all``/``drop_all``) and the CLI wiring are exercised
without a container.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from provenance.io.db import migrate

runner = CliRunner()


def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'migrate.db'}"


def test_upgrade_and_load_and_reset_on_sqlite(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path)
    migrate.upgrade(url=url)
    report = migrate.load(Path("tests/fixtures"), url=url, source_name="fixtures")
    assert not report.already_loaded
    assert report.readings_inserted > 0

    # Re-loading is idempotent.
    again = migrate.load(Path("tests/fixtures"), url=url, source_name="fixtures")
    assert again.already_loaded

    # Reset drops and rebuilds: the batch is gone, so a load runs fresh again.
    migrate.reset(url=url)
    fresh = migrate.load(Path("tests/fixtures"), url=url, source_name="fixtures")
    assert not fresh.already_loaded


def test_is_sqlite_detection() -> None:
    assert migrate._is_sqlite("sqlite+aiosqlite:///x.db")
    assert not migrate._is_sqlite("postgresql+psycopg://h/db")


def _run_cli(args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from provenance.cli.main import app
    from provenance.config.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path))
    get_settings.cache_clear()
    result = runner.invoke(app, args)
    get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    return result.output


def test_cli_db_upgrade_then_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run_cli(["db", "upgrade"], tmp_path, monkeypatch)
    out = _run_cli(["db", "load", "--source", "tests/fixtures"], tmp_path, monkeypatch)
    assert "Loaded" in out
    # Second load is a no-op.
    out2 = _run_cli(["db", "load", "--source", "tests/fixtures"], tmp_path, monkeypatch)
    assert "Already loaded" in out2


def test_cli_db_reset_requires_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from provenance.cli.main import app
    from provenance.config.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path))
    get_settings.cache_clear()
    refused = runner.invoke(app, ["db", "reset"])
    assert refused.exit_code == 1
    assert "Refusing" in refused.output
    confirmed = runner.invoke(app, ["db", "reset", "--yes"])
    assert confirmed.exit_code == 0
    get_settings.cache_clear()
