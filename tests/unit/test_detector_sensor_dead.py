"""R21 SENSOR_DEAD (a covered series that stopped and never resumed)."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.sensor_dead import SensorDeadDetector


def test_r21_flags_series_that_died(make_frame, make_ctx) -> None:
    # S1 stops after 10 hours; S2 runs 200 hours, so the window ends far later.
    rows = series_rows("S1", "PM10", [10.0] * 10) + series_rows("S2", "PM10", [20.0] * 200)
    frame = make_frame(rows)
    out = SensorDeadDetector().detect(frame, make_ctx(frame))
    assert set(out["reason_code"]) == {"R21"}
    assert set(out["station_id"]) == {"S1"}


def test_r21_negative_when_all_end_together(make_frame, make_ctx) -> None:
    rows = series_rows("S1", "PM10", [10.0] * 100) + series_rows("S2", "PM10", [20.0] * 100)
    frame = make_frame(rows)
    assert SensorDeadDetector().detect(frame, make_ctx(frame)).empty


def test_r21_boundary_just_under_trailing_threshold(make_frame, make_ctx) -> None:
    # S1 ends 71 hours before S2 -> under the 72-hour trailing threshold.
    rows = series_rows("S1", "PM10", [10.0] * 30) + series_rows("S2", "PM10", [20.0] * 101)
    frame = make_frame(rows)
    assert SensorDeadDetector().detect(frame, make_ctx(frame)).empty
