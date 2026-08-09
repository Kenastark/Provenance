"""The ``prov models`` CLI: training writes artefacts + cards, residuals persist."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from provenance.cli.main import app
from provenance.config.settings import get_settings
from provenance.models import registry

pytestmark = pytest.mark.integration

runner = CliRunner()


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    art = tmp_path / "art"
    monkeypatch.setenv("PROVENANCE_ARTEFACTS_DIR", str(art))
    monkeypatch.setenv("PROVENANCE_MODEL_DOCS_DIR", str(tmp_path / "docs"))
    get_settings.cache_clear()
    return art


def test_models_train_source_writes_artefacts_and_cards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    art = _env(monkeypatch, tmp_path)
    try:
        result = runner.invoke(app, ["models", "train", "--source", "tests/fixtures"])
        assert result.exit_code == 0, result.output
        assert "Deweather" in result.output and "Fault" in result.output
        assert registry.bundle_available(art)  # both models loadable with valid cards
        # A human-readable card was written for each model.
        docs = sorted((tmp_path / "docs").glob("*.md"))
        assert any(p.name.startswith("deweather-") for p in docs)
        assert any(p.name.startswith("fault-") for p in docs)
    finally:
        get_settings.cache_clear()


def test_models_train_demo_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    art = _env(monkeypatch, tmp_path)
    try:
        result = runner.invoke(
            app, ["models", "train", "--demo", "--stations", "6", "--days", "14"]
        )
        assert result.exit_code == 0, result.output
        assert registry.bundle_available(art)
    finally:
        get_settings.cache_clear()


def test_models_residuals_persists_to_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _env(monkeypatch, tmp_path)
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'models.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        # Train, load a drop into the DB, then compute and store residuals.
        assert runner.invoke(app, ["models", "train", "--source", "tests/fixtures"]).exit_code == 0
        assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
        assert runner.invoke(app, ["db", "load", "--source", "tests/fixtures"]).exit_code == 0
        res = runner.invoke(app, ["models", "residuals", "--source", "tests/fixtures"])
        assert res.exit_code == 0, res.output
        assert "Stored" in res.output
    finally:
        get_settings.cache_clear()


def test_models_residuals_without_models_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _env(monkeypatch, tmp_path)  # empty artefacts dir
    try:
        res = runner.invoke(app, ["models", "residuals", "--source", "tests/fixtures"])
        assert res.exit_code == 1
        assert "No trained models" in res.output
    finally:
        get_settings.cache_clear()
