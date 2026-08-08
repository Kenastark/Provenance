"""R01 ROW_ABSENT and R02 COMM_GAP."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.row_absent import CommGapDetector, RowAbsentDetector


def _drop(rows: list[dict], indices: set[int]) -> list[dict]:
    return [r for i, r in enumerate(rows) if i not in indices]


def test_r01_flags_an_interior_absent_hour(make_frame, make_ctx) -> None:
    rows = _drop(series_rows("S1", "PM10", [10.0] * 8 + [11.0]), {3})  # 9-hour span, hour 3 missing
    frame = make_frame(rows)
    out = RowAbsentDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R01"]
    assert len(out) == 1


def test_r01_negative_on_contiguous_series(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "PM10", [10.0, 11.0, 12.0, 13.0]))
    assert RowAbsentDetector().detect(frame, make_ctx(frame)).empty


def test_r01_boundary_two_gaps(make_frame, make_ctx) -> None:
    rows = _drop(series_rows("S1", "PM10", list(range(10))), {2, 7})
    frame = make_frame(rows)
    out = RowAbsentDetector().detect(frame, make_ctx(frame))
    assert len(out) == 2


def test_r02_flags_gap_at_threshold(make_frame, make_ctx) -> None:
    # comm_gap threshold is 6 hours; drop exactly 6 consecutive interior hours.
    rows = _drop(series_rows("S1", "O3", [50.0] * 20), set(range(5, 11)))
    frame = make_frame(rows)
    out = CommGapDetector().detect(frame, make_ctx(frame))
    assert list(out["reason_code"]) == ["R02"]
    assert out.iloc[0]["evidence"]["missing_ticks"] == 6


def test_r02_negative_below_threshold(make_frame, make_ctx) -> None:
    rows = _drop(series_rows("S1", "O3", [50.0] * 20), set(range(5, 10)))  # 5-hour gap
    frame = make_frame(rows)
    assert CommGapDetector().detect(frame, make_ctx(frame)).empty
