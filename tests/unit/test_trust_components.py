"""Unit tests for each trust component, in isolation."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from tests.support import series_rows

from provenance.config.loading import load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import AuditContext
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C
from provenance.trust import components as comp
from provenance.trust.weights import load_trust_weights

_WCFG = load_trust_weights()
_CLEAN = [30.0 + 10.0 * math.sin(2 * math.pi * i / 12) for i in range(48)]


def _frame(specs: list[tuple[str, str, list[float]]], **kw: object) -> pd.DataFrame:
    rows: list[dict] = []
    for station, parameter, values in specs:
        rows += series_rows(station, parameter, values, **kw)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


def _defects(frame: pd.DataFrame) -> pd.DataFrame:
    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))
    return registry.run_detectors(frame, ctx)


def _at(frame: pd.DataFrame) -> pd.Timestamp:
    return pd.Timestamp(frame[C.TIMESTAMP].max())


def _health(frame: pd.DataFrame, station: str = "S1"):
    return comp.health_conf(_defects(frame), build_coverage(frame), station, _at(frame), _WCFG)


def test_health_conf_is_one_for_a_clean_station() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])
    c, codes, _ = _health(frame)
    assert c.value == 1.0
    assert codes == []


def test_health_conf_decays_with_active_defects() -> None:
    # Three impossible PM10 values (critical) drop health well below 1.
    values = list(_CLEAN)
    values[10] = values[20] = values[30] = 5000.0
    frame = _frame([("S1", "PM10", values)])
    c, codes, _ = _health(frame)
    assert 0.0 < c.value < 1.0
    assert "T01" in codes


def test_health_conf_load_is_bounded_however_long_the_freeze() -> None:
    """The v1.0 bug: load summed one weight per flag ROW, so it grew without bound
    with window length and drove the component to ~1e-30. Load is now a fraction,
    so a freeze twice as long spoils the same 100% of the station and scores the
    same — bounded below by exp(-worst_severity / scale).
    """
    hcfg = _WCFG["health"]
    floor = math.exp(-hcfg["severity_weights"]["critical"] / hcfg["decay_scale"])

    short = _health(_frame([("S1", "PM10", [42.0] * 48)]))[0].value
    long_ = _health(_frame([("S1", "PM10", [42.0] * 96)]))[0].value

    assert short == pytest.approx(long_, abs=1e-9), "load must not scale with window length"
    assert short >= floor - 1e-9
    assert short > 1e-3, "a wholly frozen station must not saturate to zero"


def test_health_conf_scales_with_how_much_of_the_station_is_spoiled() -> None:
    """One frozen parameter out of four is less damaging than the only one frozen."""
    frozen_only = _frame([("S1", "PM10", [42.0] * 48)])
    frozen_one_of_four = _frame(
        [
            ("S1", "PM10", [42.0] * 48),
            ("S1", "NO2", _CLEAN),
            ("S1", "O3", _CLEAN),
            ("S1", "CO", _CLEAN),
        ]
    )
    assert _health(frozen_only)[0].value < _health(frozen_one_of_four)[0].value


def test_imputation_is_placeholder_and_full_for_present_data() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])
    coverage = build_coverage(frame)
    c, codes, _notes = comp.imputation_uncertainty(coverage, "S1", _at(frame), _WCFG)
    assert c.is_placeholder is True
    assert c.value == 1.0  # nothing absent -> certainty 1.0
    assert codes == []  # no caveat when nothing is missing


def test_imputation_uncertainty_rises_with_absence() -> None:
    # Drop interior hours so the trailing window sees real absence.
    values = list(_CLEAN)
    frame = _frame([("S1", "PM10", values), ("S2", "PM10", _CLEAN)])
    frame = frame[
        ~((frame[C.STATION_ID] == "S1") & (frame[C.TIMESTAMP].dt.hour.isin([20, 21, 22])))
    ]
    frame = C.validate(frame)
    coverage = build_coverage(frame)
    c, codes, notes = comp.imputation_uncertainty(coverage, "S1", _at(frame), _WCFG)
    assert c.value < 1.0
    assert "T02" in codes
    assert notes


def test_cross_sensor_consistency_high_for_correlated_peers() -> None:
    frame = _frame([("S1", "PM10", _CLEAN), ("S2", "PM10", _CLEAN), ("S3", "PM10", _CLEAN)])
    coverage = build_coverage(frame)
    c, _, _ = comp.cross_sensor_consistency(frame, coverage, "S1", _at(frame), _WCFG)
    assert c.value > 0.9


def test_cross_sensor_consistency_zero_for_a_frozen_series() -> None:
    frame = _frame([("S1", "PM10", [42.0] * 48), ("S2", "PM10", _CLEAN), ("S3", "PM10", _CLEAN)])
    coverage = build_coverage(frame)
    c, codes, _ = comp.cross_sensor_consistency(frame, coverage, "S1", _at(frame), _WCFG)
    assert c.value == 0.0
    assert "T03" in codes


def test_cross_sensor_unavailable_without_enough_peers() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])
    coverage = build_coverage(frame)
    c, codes, _ = comp.cross_sensor_consistency(frame, coverage, "S1", _at(frame), _WCFG)
    assert c.value == 0.5  # neutral, not zero
    assert "T05" in codes


def test_physical_plausibility_one_well_inside_bounds() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])
    c, _, _ = comp.physical_plausibility(
        frame, "S1", _at(frame), load_thresholds(), _defects(frame), _WCFG
    )
    assert c.value == 1.0


def test_physical_plausibility_zero_on_an_impossible_reading() -> None:
    values = list(_CLEAN)
    values[40] = 5000.0  # exceeds the PM10 physical maximum
    frame = _frame([("S1", "PM10", values)])
    c, codes, _ = comp.physical_plausibility(
        frame, "S1", _at(frame), load_thresholds(), _defects(frame), _WCFG
    )
    assert c.value == 0.0
    assert "T04" in codes


def test_severity_vs_threshold_is_one_when_clean() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])
    assert comp.severity_vs_threshold(_defects(frame), "S1", _at(frame), _WCFG) == 1.0
