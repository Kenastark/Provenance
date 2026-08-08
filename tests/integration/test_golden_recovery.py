"""The central correctness test: the audit recovers the injected ledger exactly.

The fixture generator injects each reason code a known number of times and records
that count. If the audit reports a different count for any code, a detector is
over- or under-counting, and this test fails with the per-code diff.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

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


def test_step_change_recovers_the_injected_shift_exactly(synthetic_corpus) -> None:
    """R14 must recover the injected step's size *and* its instant.

    The ledger injects a single +15.0 µg/m3 shift into NO@STA-02 at the halfway
    hour. Locating the changepoint off the CUSUM crossing put this at hour 11 —
    inside the stable pre-shift stretch — and reported a magnitude of 6.798, the
    distance from the whole-series mean at an arbitrary point. Both numbers were
    wrong while the flag count was right, which is exactly the kind of error a
    count-only assertion cannot see.
    """
    frame, ledger = synthetic_corpus
    result = run_audit(frame, now=_FIXED_NOW)
    steps = [e for e in result.notable_events if e.reason_code == "R14"]
    assert len(steps) == 1, steps
    step = steps[0]

    injected_hour = (ledger.n_days * 24) // 2
    expected_at = pd.Timestamp("2026-05-01T00:00:00") + pd.Timedelta(hours=injected_hour)
    assert step.timestamp_utc == expected_at.isoformat()
    assert step.evidence["signed_magnitude"] == pytest.approx(15.0, abs=1e-6)
    assert step.evidence["magnitude"] == pytest.approx(15.0, abs=1e-6)


def test_defect_rate_within_unit_interval(synthetic_corpus) -> None:
    frame, _ = synthetic_corpus
    result = run_audit(frame, now=_FIXED_NOW)
    assert 0.0 <= result.defect_rate.rate <= 1.0
