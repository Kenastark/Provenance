"""The central correctness test: the audit recovers the injected ledger exactly.

The fixture generator injects each reason code a known number of times and records
that count. If the audit reports a different count for any code, a detector is
over- or under-counting, and this test fails with the per-code diff.
"""

from __future__ import annotations

from datetime import UTC, datetime

from provenance.audit.orchestrator import run_audit

_FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_audit_recovers_every_injected_code_exactly(synthetic_corpus) -> None:
    frame, ledger = synthetic_corpus
    result = run_audit(frame, now=_FIXED_NOW)
    expected = ledger.to_dict()["expected_counts"]
    assert result.defects_by_code == expected


def test_clean_corpus_trips_no_detector(clean_corpus) -> None:
    result = run_audit(clean_corpus, now=_FIXED_NOW)
    assert result.defects_by_code == {}
    assert result.defect_rate.n_defective_cells == 0


def test_structural_absence_does_not_move_the_defect_rate(clean_corpus, synthetic_corpus) -> None:
    # The clean corpus carries no injected defects and no structural absence: its
    # defect rate is exactly zero.
    clean = run_audit(clean_corpus, now=_FIXED_NOW)
    assert clean.defect_rate.rate == 0.0

    # The injected corpus carries structural absences (STA-03 no NO, STA-04 no
    # groundwater). They are reported (R18/R19) but excluded from the rate: the
    # denominator is the covered cells only, never the structurally-excluded ones.
    frame, _ = synthetic_corpus
    injected = run_audit(frame, now=_FIXED_NOW)
    assert injected.coverage.n_structurally_excluded_cells > 0
    assert injected.defect_rate.n_covered_cells == injected.coverage.n_covered_cells
    counting = {"R18", "R19"}
    assert counting.isdisjoint(_counting_codes(injected)), "structural codes must not count"


def _counting_codes(result) -> set[str]:
    from provenance.config import reason_codes

    counting = {rc.code for rc in reason_codes.defect_codes()}
    return {c for c in result.defects_by_code if c in counting}


def test_defect_rate_within_unit_interval(synthetic_corpus) -> None:
    frame, _ = synthetic_corpus
    result = run_audit(frame, now=_FIXED_NOW)
    assert 0.0 <= result.defect_rate.rate <= 1.0
