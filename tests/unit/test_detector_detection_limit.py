"""R11 DETECTION_LIMIT_FLOOR (NO pinned at 0.7 µg/m3)."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.detection_limit import DetectionLimitDetector


def test_r11_flags_floor_run_at_threshold(make_frame, make_ctx) -> None:
    # detection_limit threshold is 6 hours; a run of exactly 6 at the floor trips.
    values = [10.0, 9.0] + [0.7] * 6 + [8.0]
    frame = make_frame(series_rows("S1", "NO", values))
    out = DetectionLimitDetector().detect(frame, make_ctx(frame))
    assert set(out["reason_code"]) == {"R11"}
    assert len(out) == 6


def test_r11_negative_when_above_floor(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "NO", [10.0, 9.0, 8.0, 7.0]))
    assert DetectionLimitDetector().detect(frame, make_ctx(frame)).empty


def test_r11_boundary_short_run_not_flagged(make_frame, make_ctx) -> None:
    values = [10.0] + [0.7] * 5 + [9.0]  # only 5 consecutive floor values
    frame = make_frame(series_rows("S1", "NO", values))
    assert DetectionLimitDetector().detect(frame, make_ctx(frame)).empty
