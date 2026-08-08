"""Trust Score v1: the properties the phase gate names, plus the standing-rule-9
invariant that a score cannot exist without its explanation."""

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
from provenance.trust.engine import compute_trust, latest_timestamp
from provenance.trust.score import Risk, TrustComponent, TrustScore

_CLEAN = [30.0 + 10.0 * math.sin(2 * math.pi * i / 12) for i in range(48)]


def _frame(specs: list[tuple[str, list[float]]]) -> pd.DataFrame:
    return _frame_multi([(station, "PM10", values) for station, values in specs])


def _frame_multi(specs: list[tuple[str, str, list[float]]]) -> pd.DataFrame:
    rows: list[dict] = []
    for station, parameter, values in specs:
        rows += series_rows(station, parameter, values)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


def _score(frame: pd.DataFrame, station: str) -> TrustScore:
    coverage = build_coverage(frame)
    ctx = AuditContext(thresholds=load_thresholds(), coverage=coverage)
    defects = registry.run_detectors(frame, ctx)
    return compute_trust(frame, defects, station, latest_timestamp(frame), coverage=coverage)


def test_perfect_station_scores_above_0_95() -> None:
    frame = _frame([("S1", _CLEAN), ("S2", _CLEAN), ("S3", _CLEAN)])
    score = _score(frame, "S1")
    assert score.value > 0.95, score.to_dict()


def test_frozen_station_scores_below_0_5() -> None:
    frame = _frame([("S1", [42.0] * 48), ("S2", _CLEAN), ("S3", _CLEAN)])
    score = _score(frame, "S1")
    assert score.value < 0.5, score.to_dict()


def test_health_conf_still_discriminates_between_degrees_of_broken() -> None:
    """The threshold gates above pass under saturation as easily as under
    calibration, which is how v1.0 shipped a HealthConf that was ~1e-30 for every
    station in the real network. This asserts the property those gates cannot:
    that the component still *ranks* stations rather than flooring them all.
    """
    spike = list(_CLEAN)
    spike[10] = 5000.0  # one impossible reading
    frame = _frame([("S1", _CLEAN), ("S2", spike), ("S3", [42.0] * 48), ("S4", _CLEAN)])
    health = {
        station: next(c.value for c in _score(frame, station).components if c.name == "HealthConf")
        for station in ("S1", "S2", "S3")
    }
    assert health["S1"] > health["S2"] > health["S3"], health
    # And the spread is usable, not three numbers crushed against zero.
    assert health["S2"] > 1e-3, health
    assert health["S3"] > 1e-6, health


def test_a_station_losing_one_parameter_stays_more_trusted_than_one_wholly_frozen() -> None:
    partial = _frame_multi(
        [("S1", "PM10", [42.0] * 48), ("S1", "NO2", _CLEAN), ("S1", "O3", _CLEAN)]
        + [(s, p, _CLEAN) for s in ("S2", "S3") for p in ("PM10", "NO2", "O3")]
    )
    whole = _frame([("S1", [42.0] * 48), ("S2", _CLEAN), ("S3", _CLEAN)])
    assert _score(partial, "S1").value > _score(whole, "S1").value


def test_every_score_carries_components_and_a_reason_code() -> None:
    frame = _frame([("S1", _CLEAN), ("S2", _CLEAN), ("S3", _CLEAN)])
    score = _score(frame, "S1")
    assert len(score.components) == 4
    assert score.reason_codes
    d = score.to_dict()
    assert d["components"] and d["reason_codes"]


def test_component_weights_sum_to_one() -> None:
    frame = _frame([("S1", _CLEAN), ("S2", _CLEAN), ("S3", _CLEAN)])
    score = _score(frame, "S1")
    assert math.isclose(sum(c.weight for c in score.components), 1.0, abs_tol=1e-9)


def test_risk_carries_the_population_exposure_stub_flag() -> None:
    frame = _frame([("S1", _CLEAN), ("S2", _CLEAN), ("S3", _CLEAN)])
    score = _score(frame, "S1")
    assert score.risk.population_exposure_stubbed is True
    assert score.risk.population_exposure == 1.0


def test_trust_score_refuses_to_construct_without_components() -> None:
    risk = Risk(value=1.0, trust=1.0, severity_vs_threshold=1.0, population_exposure=1.0)
    with pytest.raises(ValueError, match="component breakdown"):
        TrustScore(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            value=1.0,
            components=[],
            reason_codes=["T00"],
            risk=risk,
        )


def test_trust_score_refuses_to_construct_without_a_reason_code() -> None:
    risk = Risk(value=1.0, trust=1.0, severity_vs_threshold=1.0, population_exposure=1.0)
    comp = TrustComponent(name="HealthConf", value=1.0, weight=0.35)
    with pytest.raises(ValueError, match="reason code"):
        TrustScore(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            value=1.0,
            components=[comp],
            reason_codes=[],
            risk=risk,
        )


def test_trust_value_must_be_in_unit_interval() -> None:
    risk = Risk(value=1.0, trust=1.0, severity_vs_threshold=1.0, population_exposure=1.0)
    comp = TrustComponent(name="HealthConf", value=1.0, weight=0.35)
    with pytest.raises(ValueError, match="outside"):
        TrustScore(
            station_id="S1",
            timestamp_utc="2026-05-01T00:00:00",
            value=1.5,
            components=[comp],
            reason_codes=["T00"],
            risk=risk,
        )
