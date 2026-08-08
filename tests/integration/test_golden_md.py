"""Snapshot the rendered audit.md against a committed golden file.

A readable diff on failure makes an unintended change to the report obvious in
review, rather than silently altering the document a judge would read.
"""

from __future__ import annotations

import difflib
from datetime import UTC, datetime
from pathlib import Path

from provenance.audit.orchestrator import run_audit
from provenance.fixtures.generator import generate
from provenance.report.render import render_markdown

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden" / "audit.md"
_FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _current() -> str:
    frame, _ = generate()
    return render_markdown(run_audit(frame, now=_FIXED_NOW))


def test_audit_md_matches_golden() -> None:
    assert GOLDEN.exists(), (
        f"Golden file missing: {GOLDEN}. Regenerate with "
        "`python -m tests.fixtures.golden.regenerate` (see the file's docstring)."
    )
    expected = GOLDEN.read_text(encoding="utf-8")
    actual = _current()
    if actual != expected:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(), actual.splitlines(), "golden", "actual", lineterm=""
            )
        )
        raise AssertionError("audit.md drifted from the golden snapshot:\n" + diff)
