"""Property-based invariants for the wind graph.

Hypothesis sweeps the geometry and the wind so the guarantees hold everywhere, not
just at the cardinal points the unit tests pin.
"""

from __future__ import annotations

import math

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from provenance.config.loading import load_graph_config
from provenance.graph import scenarios as S
from provenance.graph.build import build_snapshot
from provenance.graph.edges import WindEdgeParams, wind_edge_weight
from provenance.graph.snapshot import EdgeType
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField

CFG = load_graph_config()
PARAMS = WindEdgeParams.from_config(CFG)

_lat = st.floats(min_value=47.40, max_value=47.70)
_lon = st.floats(min_value=21.40, max_value=21.70)
_bearing = st.floats(min_value=0.0, max_value=360.0)
_speed = st.floats(min_value=0.0, max_value=25.0)


@given(_lat, _lon, _lat, _lon, _bearing, _speed)
@settings(max_examples=300, deadline=None)
def test_weight_is_finite_and_nonnegative(la, lo, lb, ln, wind_from, speed) -> None:
    w = wind_edge_weight(la, lo, lb, ln, wind_from, speed, PARAMS)
    assert math.isfinite(w)
    assert w >= 0.0


@given(_lat, _lon, _lat, _lon, _bearing, _speed)
@settings(max_examples=300, deadline=None)
def test_weight_is_a_pure_function(la, lo, lb, ln, wind_from, speed) -> None:
    a = wind_edge_weight(la, lo, lb, ln, wind_from, speed, PARAMS)
    b = wind_edge_weight(la, lo, lb, ln, wind_from, speed, PARAMS)
    assert a == b  # deterministic in (geometry, wind, config)


@given(_bearing, st.floats(min_value=0.5, max_value=20.0))
@settings(max_examples=200, deadline=None)
def test_weight_monotone_in_distance(wind_from, speed) -> None:
    # A fixed source and bearing; step the neighbour away and the weight never rises.
    src = (47.53, 21.55)
    prev = math.inf
    for dlon in (0.01, 0.03, 0.06, 0.10):
        w = wind_edge_weight(src[0], src[1], src[0], src[1] + dlon, wind_from, speed, PARAMS)
        assert w <= prev + 1e-12
        prev = w


@given(st.floats(min_value=0.5, max_value=20.0))
@settings(max_examples=100, deadline=None)
def test_weight_monotone_in_angular_offset(speed) -> None:
    # SRC→EAST bearing ~90°; sweep the wind's travel direction off that bearing.
    src = (47.53, 21.55)
    dst = (47.53, 21.59)
    prev = math.inf
    for off in range(0, 110, 10):
        wind_from = (90.0 - off + 180.0) % 360.0
        w = wind_edge_weight(src[0], src[1], dst[0], dst[1], wind_from, speed, PARAMS)
        assert w <= prev + 1e-12
        prev = w


@given(st.integers(min_value=0, max_value=71))
@settings(max_examples=40, deadline=None)
def test_snapshot_over_corpus_is_finite_and_deterministic(hour) -> None:
    # Build the graph at every hour of a scenario corpus (which carries real wind):
    # every snapshot is finite and byte-identical on a rebuild.
    scenario = S.corroborated_plume()
    points = [StationPoint(p.station_id, p.lat, p.lon) for p in scenario.points]
    wind = WindField.from_frame(scenario.frame)
    start = scenario.frame["timestamp_utc"].min()
    at = pd.Timestamp(start) + pd.Timedelta(hours=hour)
    a = build_snapshot(points, wind, at, CFG)
    b = build_snapshot(points, wind, at, CFG)
    assert a.has_nan() is False
    pd.testing.assert_frame_equal(
        a.edge_table(EdgeType.WIND_CONDITIONED), b.edge_table(EdgeType.WIND_CONDITIONED)
    )
