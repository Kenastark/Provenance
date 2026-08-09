"""The model-drift monitor's pure logic (§11, phase 7)."""

from __future__ import annotations

import pytest

from provenance.ops import drift

pytestmark = pytest.mark.unit


def test_empty_series_is_unknown_not_a_fabricated_trend() -> None:
    s = drift.drift_series("x", "unit", [])
    assert s.direction == "unknown"
    assert s.latest is None and s.baseline is None


def test_drift_series_summarises_direction_and_delta() -> None:
    pts = [drift.DriftPoint("t0", 0.90), drift.DriftPoint("t1", 0.80)]
    s = drift.drift_series("deweather_r2", "r2", pts)
    assert s.baseline == 0.90
    assert s.latest == 0.80
    assert s.delta == pytest.approx(-0.10)
    assert s.direction == "down"


def test_defect_rate_drift_by_station_uses_covered_cells_as_denominator() -> None:
    runs = [
        drift.RunStationCounts(
            run_id="ar1",
            generated_at="2026-06-01T00:00:00",
            counting_defects={"STA-01": 1},
            covered_cells={"STA-01": 100, "STA-02": 100},
        ),
        drift.RunStationCounts(
            run_id="ar2",
            generated_at="2026-06-08T00:00:00",
            counting_defects={"STA-01": 5},
            covered_cells={"STA-01": 100, "STA-02": 100},
        ),
    ]
    series = drift.defect_rate_drift_by_station(runs)
    sta01 = series["STA-01"]
    assert [p.value for p in sta01.points] == [1.0, 5.0]  # percent
    assert sta01.direction == "up"
    # A station with no defects stays flat at zero.
    assert series["STA-02"].latest == 0.0


def test_conformal_coverage_drift_annotates_the_nominal_target() -> None:
    s = drift.conformal_coverage_drift([("t0", 0.91), ("t1", 0.88)], nominal=0.9)
    assert "0.9" in s.note
    assert s.direction == "down"
