"""R07 EXCEEDS_PHYSICAL_MAX and R08 BELOW_PHYSICAL_MIN."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.physical_bounds import BelowMinDetector, ExceedsMaxDetector


def test_r07_flags_value_over_max(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [30.0, 3000.0, 40.0]))  # max is 2000
    out = ExceedsMaxDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R07"]
    assert out.iloc[0]["evidence"]["value"] == 3000.0


def test_r07_negative_within_bounds(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [30.0, 40.0, 1999.0]))
    assert ExceedsMaxDetector().detect(frame, make_ctx(frame)).empty


def test_r07_boundary_exactly_at_max_not_flagged(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [2000.0, 2000.01]))
    out = ExceedsMaxDetector().detect(frame, make_ctx(frame))
    assert len(out) == 1  # only the 2000.01 trips; 2000.0 exactly is allowed


def test_r08_flags_value_below_min(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterTemp", [13.0, -10.0], unit="celsius"))
    out = BelowMinDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R08"]


def test_r08_negative_within_bounds(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterTemp", [12.0, 13.0, 14.0], unit="celsius"))
    assert BelowMinDetector().detect(frame, make_ctx(frame)).empty


def test_r08_boundary_exactly_at_min_not_flagged(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterTemp", [-5.0, -5.01], unit="celsius"))
    out = BelowMinDetector().detect(frame, make_ctx(frame))
    assert len(out) == 1
