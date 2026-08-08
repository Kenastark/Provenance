"""R14 STEP_CHANGE (CUSUM control chart)."""

from __future__ import annotations

import numpy as np
from tests.support import series_rows

from provenance.detectors.step_change import StepChangeDetector


def test_r14_flags_sustained_shift(make_frame, make_ctx) -> None:
    values = [10.0] * 40 + [30.0] * 40  # a clear, sustained level shift
    frame = make_frame(series_rows("S1", "NO", values))
    out = StepChangeDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R14"]
    # The shift is detected exactly once; its magnitude is real (not zero).
    assert out.iloc[0]["evidence"]["magnitude"] > 0
    assert out.iloc[0]["evidence"]["direction"] in {"upward", "downward"}


def test_r14_negative_on_stationary_series(make_frame, make_ctx) -> None:
    t = np.arange(80)
    values = list(50 + 5 * np.sin(2 * np.pi * t / 12))  # mean-reverting, no shift
    frame = make_frame(series_rows("S1", "O3", values))
    assert StepChangeDetector().detect(frame, make_ctx(frame)).empty


def test_r14_boundary_too_few_points(make_frame, make_ctx) -> None:
    values = [10.0] * 5 + [30.0] * 5  # below the 24-point minimum
    frame = make_frame(series_rows("S1", "NO", values))
    assert StepChangeDetector().detect(frame, make_ctx(frame)).empty


def test_r14_ignores_out_of_bounds_spike(make_frame, make_ctx) -> None:
    # A lone physically-impossible spike is R07's job, not a step change.
    values = [10.0] * 40 + [3000.0] + [10.0] * 39
    frame = make_frame(series_rows("S1", "PM10", values))
    assert StepChangeDetector().detect(frame, make_ctx(frame)).empty
