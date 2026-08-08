"""Determinism: two runs over the same input produce byte-identical output.

Standing rule 8. The only field allowed to differ between runs is the wall-clock
``generated_at`` timestamp, which is excluded from the comparison.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from provenance.audit.orchestrator import run_audit
from provenance.fixtures.generator import generate
from provenance.report.render import render_json, render_markdown


def _strip_time(blob: str) -> dict:
    data = json.loads(blob)
    data["meta"].pop("generated_at", None)
    return data


def test_audit_json_is_byte_identical_excluding_timestamp(synthetic_corpus) -> None:
    frame, _ = synthetic_corpus
    a = render_json(run_audit(frame, now=datetime(2026, 1, 1, tzinfo=UTC)))
    b = render_json(run_audit(frame, now=datetime(2030, 9, 9, tzinfo=UTC)))
    assert _strip_time(a) == _strip_time(b)


def test_two_generations_produce_identical_corpora() -> None:
    f1, _ = generate()
    f2, _ = generate()
    assert f1.equals(f2)


def test_markdown_is_deterministic_for_fixed_now(synthetic_corpus) -> None:
    frame, _ = synthetic_corpus
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert render_markdown(run_audit(frame, now=now)) == render_markdown(run_audit(frame, now=now))
