from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from provenance.cli.main import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_codes_list() -> None:
    result = runner.invoke(app, ["codes", "list"])
    assert result.exit_code == 0
    assert "R07" in result.stdout


def test_codes_show() -> None:
    result = runner.invoke(app, ["codes", "show", "r12"])
    assert result.exit_code == 0


def test_fixtures_make_and_audit_run_write_all_three_reports(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    reports = tmp_path / "reports"
    make = runner.invoke(app, ["fixtures", "make", "--out", str(fixtures)])
    assert make.exit_code == 0, make.output
    assert (fixtures / "corpus.parquet").exists()

    run = runner.invoke(app, ["audit", "run", "--data", str(fixtures), "--out", str(reports)])
    assert run.exit_code == 0, run.output
    for name in ("audit.json", "audit.md", "audit.html"):
        assert (reports / name).exists(), f"{name} not written"


def test_data_profile_on_fixture(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    runner.invoke(app, ["fixtures", "make", "--out", str(fixtures)])
    result = runner.invoke(app, ["data", "profile", "--data", str(fixtures)])
    assert result.exit_code == 0
    assert "readings" in result.stdout


def test_audit_report_prints_markdown(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    reports = tmp_path / "reports"
    runner.invoke(app, ["fixtures", "make", "--out", str(fixtures)])
    runner.invoke(app, ["audit", "run", "--data", str(fixtures), "--out", str(reports)])
    result = runner.invoke(app, ["audit", "report", "--out", str(reports)])
    assert result.exit_code == 0
    assert "Provenance audit" in result.stdout


def test_audit_report_without_run_errors(tmp_path: Path) -> None:
    result = runner.invoke(app, ["audit", "report", "--out", str(tmp_path)])
    assert result.exit_code != 0


def test_schema_observe_writes_manifest(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    manifests = tmp_path / "manifests"
    runner.invoke(app, ["fixtures", "make", "--out", str(fixtures)])
    result = runner.invoke(
        app, ["schema", "observe", "--data", str(fixtures), "--manifests", str(manifests)]
    )
    assert result.exit_code == 0
    assert list(manifests.glob("observed-schema-*.json"))
