"""Structural invariants.

These tests exist because the standing rules in CLAUDE.md are easy to agree with
and easy to violate under deadline pressure. Anything that can be checked
mechanically is checked here rather than left to review.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "provenance"
REPO = Path(__file__).resolve().parents[2]

# Upstream layer -> layers it must never import.
# The pipeline runs io -> schema -> grid -> detectors -> audit -> trust -> graph
# -> models -> explain, with api and report as presentation only. A detector that
# imports the API has stopped being a pure function over frames.
FORBIDDEN: dict[str, set[str]] = {
    "detectors": {"api", "report", "models", "graph"},
    "grid": {"api", "report", "models", "graph", "detectors"},
    "schema": {"api", "report", "models", "graph", "detectors", "audit"},
    "io": {"api", "report", "models", "graph"},
    "audit": {"api", "report"},
    "trust": {"api", "report"},
    # graph sits after trust and before the neural stack: it may lean on everything
    # upstream (io/schema/grid/detectors/audit/trust/config) but never the
    # presentation layers or anything downstream of it.
    "graph": {"api", "report", "models", "explain"},
    "config": {"api", "report", "models", "graph", "detectors", "audit", "io"},
}


def _imports(path: Path) -> set[str]:
    """Return the provenance submodules imported by a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("provenance."):
                    found.add(alias.name.split(".")[1])
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("provenance.")
        ):
            found.add(node.module.split(".")[1])
    return found


def _python_files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_layer_does_not_import_downstream(package: str) -> None:
    forbidden = FORBIDDEN[package]
    for path in _python_files(package):
        offending = _imports(path) & forbidden
        assert not offending, (
            f"{path.relative_to(REPO)} imports {sorted(offending)}, which is downstream of "
            f"'{package}'. Move the shared code up the pipeline instead."
        )


def test_src_never_imports_notebooks() -> None:
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import notebooks" not in text and "from notebooks" not in text, (
            f"{path.relative_to(REPO)} imports from notebooks/. Notebooks are exploratory "
            "and must never be a dependency of shipped code."
        )


def test_no_data_files_are_tracked() -> None:
    """Data files must never be tracked by git.

    Real data is expected to exist on disk locally (see data/README.md and
    SETUP.md step 6) but must never enter git history. This checks git's index,
    not the filesystem - untracked local data is normal and required from
    phase 1 onward.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "data/raw", "data/interim", "data/processed"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [
        line for line in result.stdout.splitlines() if not line.endswith((".gitkeep", "README.md"))
    ]
    assert not tracked, (
        f"Data files are tracked by git: {tracked}. "
        "Data belongs outside git history - see data/README.md."
    )


def test_thresholds_declare_their_status() -> None:
    """A threshold file that silently pretends to be calibrated is worse than none."""
    import yaml

    cfg = yaml.safe_load((SRC / "config" / "thresholds.yaml").read_text())
    assert cfg["status"] in {"placeholder", "calibrated"}


def test_schema_assumptions_declare_their_status() -> None:
    import yaml

    cfg = yaml.safe_load((SRC / "config" / "schema_assumptions.yaml").read_text())
    assert cfg["status"] in {"unconfirmed", "confirmed"}
