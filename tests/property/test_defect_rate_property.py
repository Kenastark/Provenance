"""Defect-rate properties: bounded, and monotonic in injected defect count."""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from tests.support import series_rows

from provenance.audit.orchestrator import run_audit
from provenance.detectors.cross_param import CrossParamInversionDetector
from provenance.fixtures.generator import generate
from provenance.schema import canonical as C


@settings(max_examples=12, deadline=None)
@given(n_days=st.integers(min_value=3, max_value=12))
def test_rate_is_in_unit_interval_clean(n_days: int) -> None:
    frame, _ = generate(n_days=n_days, inject=False)
    result = run_audit(frame)
    assert 0.0 <= result.defect_rate.rate <= 1.0


def test_rate_is_in_unit_interval_injected() -> None:
    frame, _ = generate()
    assert 0.0 <= run_audit(frame).defect_rate.rate <= 1.0


def _corpus_with_inversions(k: int) -> pd.DataFrame:
    # A varying (non-frozen) series pair with exactly k injected PM2.5 > PM10
    # inversions and no other defects, so defective cells == k.
    n = 60
    wave = [10.0 * np.sin(2 * np.pi * i / 12) for i in range(n)]
    pm10 = [40.0 + w for w in wave]
    pm25 = [0.45 * v for v in pm10]  # subset of PM10 by construction
    for i in range(k):
        pm25[i] = pm10[i] + 5.0  # exceeds PM10
    rows = series_rows("S1", "PM10", pm10) + series_rows("S1", "PM2.5", pm25)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.SOURCE_FILE] = "prop_air.csv"
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


@settings(max_examples=12, deadline=None)
@given(a=st.integers(min_value=0, max_value=10), b=st.integers(min_value=0, max_value=10))
def test_rate_monotonic_in_injected_defects(a: int, b: int) -> None:
    lo, hi = sorted((a, b))
    r_lo = run_audit(_corpus_with_inversions(lo)).defect_rate
    r_hi = run_audit(_corpus_with_inversions(hi)).defect_rate
    # Same grid (denominator fixed); more injected inversions cannot lower the rate.
    assert r_hi.n_covered_cells == r_lo.n_covered_cells
    assert r_hi.rate >= r_lo.rate


@settings(max_examples=1, deadline=None)
@given(st.just(0))
def test_r09_raises_zero_flags_when_ordering_holds(_: int) -> None:
    # Clean corpus: PM2.5 = 0.45 * PM10 by construction, so R09 must be silent.
    from provenance.config.loading import load_thresholds
    from provenance.detectors.base import AuditContext
    from provenance.grid.coverage import build_coverage

    frame, _l = generate(inject=False)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))
    assert CrossParamInversionDetector().detect(frame, ctx).empty
