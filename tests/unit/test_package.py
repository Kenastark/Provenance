"""Smoke tests. If these fail, nothing else is worth reading."""

from __future__ import annotations

import provenance


def test_version_is_exposed() -> None:
    assert provenance.__version__


def test_version_matches_pyproject() -> None:
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert provenance.__version__ == declared
