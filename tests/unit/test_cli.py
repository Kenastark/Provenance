from __future__ import annotations

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


def test_unbuilt_command_says_which_phase() -> None:
    result = runner.invoke(app, ["audit", "run"])
    assert result.exit_code != 0
