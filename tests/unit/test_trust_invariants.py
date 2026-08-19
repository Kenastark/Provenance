"""Invariants that pin the engineering-judgement trust formulas.

The v1 weights are elicited, not fitted, and the component formulas (HealthConf's
exponential decay, the plausibility upper-margin softening, the cross-sensor
mapping) are judgement calls. These tests turn the *intended qualitative
behaviour* into contracts, so a later tweak that breaks the intent fails loudly
rather than silently shifting the product's central number. They do not assert the
exact magic constants — they assert the shape the constants are meant to produce.
"""

from __future__ import annotations

import math

import pandas as pd
from tests.support import series_rows

from provenance.config.loading import load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import AuditContext
from provenance.grid.coverage import build_coverage
from provenance.schema import canonical as C
from provenance.trust import components as comp
from provenance.trust.engine import compute_trust, latest_timestamp, scoring_instants
from provenance.trust.weights import load_trust_weights

_WCFG = load_trust_weights()
_CLEAN = [30.0 + 10.0 * math.sin(2 * math.pi * i / 12) for i in range(48)]


def _frame(specs: list[tuple[str, str, list[float]]]) -> pd.DataFrame:
    rows: list[dict] = []
    for station, parameter, values in specs:
        rows += series_rows(station, parameter, values)
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    return C.validate(C.add_row_hash(frame))


def _defects(frame: pd.DataFrame) -> pd.DataFrame:
    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))
    return registry.run_detectors(frame, ctx)


def _at(frame: pd.DataFrame) -> pd.Timestamp:
    return pd.Timestamp(frame[C.TIMESTAMP].max())


# --- HealthConf: monotone-decreasing in defect load -------------------------
def test_health_conf_strictly_decreases_as_impossible_readings_accumulate() -> None:
    values: list[list[float]] = []
    base = list(_CLEAN)
    for n in range(4):  # 0, 1, 2, 3 physical-max exceedances
        v = list(base)
        for i in range(n):
            v[10 + i] = 5000.0
        values.append(v)
    scores = []
    for v in values:
        frame = _frame([("S1", "PM10", v)])
        c, _, _ = comp.health_conf(_defects(frame), "S1", _at(frame), _WCFG)
        scores.append(c.value)
    # Strictly decreasing: each additional critical defect lowers HealthConf.
    assert all(scores[i] > scores[i + 1] for i in range(len(scores) - 1)), scores
    assert scores[0] == 1.0


def test_severity_costs_more_than_a_lower_severity_for_the_same_count() -> None:
    weights = _WCFG["health"]["severity_weights"]
    assert weights["critical"] > weights["high"] > weights["medium"] > weights["low"]


def test_severity_vs_threshold_rises_with_worse_defects() -> None:
    clean = _frame([("S1", "PM10", _CLEAN)])
    assert comp.severity_vs_threshold(_defects(clean), "S1", _at(clean), _WCFG) == 1.0
    bad = list(_CLEAN)
    bad[10] = 5000.0  # a critical R07
    fb = _frame([("S1", "PM10", bad)])
    assert comp.severity_vs_threshold(_defects(fb), "S1", _at(fb), _WCFG) > 1.0


# --- PhysicalPlausibility: 1 inside, softens near ceiling, 0 outside ---------
def test_plausibility_softens_near_the_ceiling_and_zeroes_beyond_it() -> None:
    th = load_thresholds()
    hi = th["physical_bounds"]["PM10"]["max"]  # 2000
    inside = _frame([("S1", "PM10", [30.0] * 48)])
    near = _frame([("S1", "PM10", [hi - 1.0] * 48)])  # crowding the ceiling
    over = _frame([("S1", "PM10", [hi + 1.0] * 48)])  # beyond it
    v_inside = comp.physical_plausibility(inside, "S1", _at(inside), th, _defects(inside), _WCFG)[0]
    v_near = comp.physical_plausibility(near, "S1", _at(near), th, _defects(near), _WCFG)[0]
    v_over = comp.physical_plausibility(over, "S1", _at(over), th, _defects(over), _WCFG)[0]
    assert v_inside.value == 1.0
    assert 0.0 <= v_near.value < 1.0
    assert v_over.value == 0.0


# --- Trust integrity: value is exactly the weighted sum, clamped -------------
def test_trust_is_the_weighted_sum_of_its_components() -> None:
    frame = _frame([("S1", "PM10", _CLEAN), ("S2", "PM10", _CLEAN), ("S3", "PM10", _CLEAN)])
    coverage = build_coverage(frame)
    score = compute_trust(frame, _defects(frame), "S1", latest_timestamp(frame), coverage=coverage)
    weighted_sum = sum(c.contribution for c in score.components)
    assert score.value == min(max(round(weighted_sum, 6), 0.0), 1.0) or math.isclose(
        score.value, weighted_sum, abs_tol=1e-6
    )


# --- scoring_instants: cadence, cap, ordering, anchor -----------------------
def test_scoring_instants_are_capped_ordered_and_anchored() -> None:
    frame = _frame([("S1", "PM10", _CLEAN)])  # 48 hourly points
    end = latest_timestamp(frame)
    daily = scoring_instants(frame, cadence_hours=24, max_points=120)
    assert daily == sorted(daily)  # ascending
    assert daily[-1] == end  # anchored on the last reading
    assert len(daily) == 2  # 48h at 24h cadence -> 2 instants
    # The cap keeps the most recent points.
    capped = scoring_instants(frame, cadence_hours=1, max_points=5)
    assert len(capped) == 5
    assert capped[-1] == end
