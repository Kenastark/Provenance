"""R10 UNIT_INCONSISTENT (CO2 labelled µg/m3 where the range is ppm)."""

from __future__ import annotations

from tests.support import series_rows

from provenance.detectors.unit_consistency import UnitInconsistentDetector


def test_r10_flags_mislabelled_series(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "CO2", [450.0, 500.0, 480.0], unit="µg/m3"))
    out = UnitInconsistentDetector().detect(frame, make_ctx(frame))
    assert set(out["reason_code"]) == {"R10"}
    assert len(out) == 3  # every cell of the mislabelled series
    assert out.iloc[0]["evidence"]["inferred"] == "ppm"


def test_r10_negative_when_unit_matches_range(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "CO2", [450.0, 500.0], unit="ppm"))
    assert UnitInconsistentDetector().detect(frame, make_ctx(frame)).empty


def test_r10_boundary_range_outside_inferred(make_frame, make_ctx) -> None:
    # Declared µg/m3 but the median (~50) is below the ppm inferred range, so not flagged.
    frame = make_frame(series_rows("S1", "CO2", [40.0, 50.0, 60.0], unit="µg/m3"))
    assert UnitInconsistentDetector().detect(frame, make_ctx(frame)).empty
