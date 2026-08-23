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


def test_models_train_hstgat_skip_if_cached_reuses_matching_artefact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`make demo-real` relies on this: a valid cached artefact for the exact data
    drop (by content checksum) is reused rather than retrained, but only when
    ``--skip-if-cached`` is passed - the default (what ``demo-real-hstgat`` run
    directly still uses) always retrains."""
    from provenance.fixtures.generator import write_corpus

    art = _env(monkeypatch, tmp_path)
    source = tmp_path / "drop"
    write_corpus(source, seed=1, n_days=14, n_stations=4)
    args = [
        "models",
        "train-hstgat",
        "--source",
        str(source),
        "--target",
        "PM10",
        "--no-baseline",
        "--epochs",
        "1",
    ]
    try:
        first = runner.invoke(app, args)
        assert first.exit_code == 0, first.output
        assert "Training HST-GAT on" in first.output
        artefacts = sorted(art.glob("hst-gat-*.pt"))
        assert len(artefacts) == 1
        trained_at = artefacts[0].stat().st_mtime

        second = runner.invoke(app, [*args, "--skip-if-cached"])
        assert second.exit_code == 0, second.output
        assert "already cached" in second.output
        assert "Training HST-GAT on" not in second.output
        artefacts_after = sorted(art.glob("hst-gat-*.pt"))
        assert len(artefacts_after) == 1
        assert artefacts_after[0].stat().st_mtime == trained_at  # reused, not rewritten

        third = runner.invoke(app, args)  # default: no --skip-if-cached
        assert third.exit_code == 0, third.output
        assert "Training HST-GAT on" in third.output  # always retrains without the flag
    finally:
        get_settings.cache_clear()


def test_models_train_imputation_skip_if_cached_reuses_matching_artefacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mirrors `test_models_train_hstgat_skip_if_cached_reuses_matching_artefact`: a
    valid cached artefact per parameter is reused with `--skip-if-cached`, and the
    default (no flag) always retrains."""
    from provenance.fixtures.generator import write_corpus

    art = _env(monkeypatch, tmp_path)
    source = tmp_path / "drop"
    write_corpus(source, seed=1, n_days=14, n_stations=4)
    args = [
        "models",
        "train-imputation",
        "--source",
        str(source),
        "--no-baseline",
        "--epochs",
        "1",
    ]
    try:
        first = runner.invoke(app, args)
        assert first.exit_code == 0, first.output
        assert "Training imputation model on" in first.output
        artefacts = sorted(art.glob("imputation-*.pt"))
        assert len(artefacts) >= 1
        trained_at = {p.name: p.stat().st_mtime for p in artefacts}

        second = runner.invoke(app, [*args, "--skip-if-cached"])
        assert second.exit_code == 0, second.output
        assert "already cached" in second.output
        assert "Training imputation model on" not in second.output
        artefacts_after = sorted(art.glob("imputation-*.pt"))
        assert len(artefacts_after) == len(artefacts)
        assert {p.name: p.stat().st_mtime for p in artefacts_after} == trained_at

        third = runner.invoke(app, args)  # default: no --skip-if-cached
        assert third.exit_code == 0, third.output
        assert "Training imputation model on" in third.output
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
