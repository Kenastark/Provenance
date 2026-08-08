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


def test_r14_signed_magnitude_agrees_with_the_direction_of_the_step(make_frame, make_ctx) -> None:
    """The evidence must not contradict the data it describes.

    A `direction` string derived from which CUSUM arm crossed first could call an
    upward step "downward"; a signed shift is read off the values themselves.
    """
    up = make_frame(series_rows("S1", "NO", [10.0] * 40 + [30.0] * 40))
    down = make_frame(series_rows("S1", "NO", [30.0] * 40 + [10.0] * 40))

    up_ev = StepChangeDetector().detect(up, make_ctx(up)).iloc[0]["evidence"]
    down_ev = StepChangeDetector().detect(down, make_ctx(down)).iloc[0]["evidence"]

    assert up_ev["signed_magnitude"] > 0, up_ev
    assert down_ev["signed_magnitude"] < 0, down_ev
    assert "direction" not in up_ev, "the ambiguous label must be gone, not merely wrong"
    assert up_ev["magnitude"] == abs(up_ev["signed_magnitude"])


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
