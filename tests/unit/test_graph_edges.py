"""The wind-conditioned edge weight — the four analytic properties that matter."""

from __future__ import annotations

import math

import pytest

from provenance.config.loading import load_graph_config
from provenance.graph.edges import (
    WindEdgeParams,
    distance_decay,
    speed_response,
    wind_edge_weight,
)

# A source and three neighbours on cardinal bearings from it.
SRC = (47.53, 21.55)
EAST = (47.53, 21.59)  # bearing ~90° from SRC
NORTH = (47.57, 21.55)  # bearing ~0°
WEST = (47.53, 21.51)  # bearing ~270°


@pytest.fixture
def params() -> WindEdgeParams:
    return WindEdgeParams.from_config(load_graph_config())


def _w(
    src: tuple[float, float], dst: tuple[float, float], wind_from: float, speed: float, p
) -> float:
    return wind_edge_weight(src[0], src[1], dst[0], dst[1], wind_from, speed, p)


def test_aligned_wind_is_maximum(params: WindEdgeParams) -> None:
    # Wind FROM the west (270°) blows toward the east; the eastern neighbour is dead
    # downwind, so its directional term is the maximum (1.0) and no other cardinal beats it.
    aligned = _w(SRC, EAST, 270.0, 5.0, params)
    north = _w(SRC, NORTH, 270.0, 5.0, params)
    west = _w(SRC, WEST, 270.0, 5.0, params)
    assert aligned > north
    assert aligned > west


def test_perpendicular_wind_is_near_zero(params: WindEdgeParams) -> None:
    aligned = _w(SRC, EAST, 270.0, 5.0, params)
    perpendicular = _w(SRC, NORTH, 270.0, 5.0, params)  # bearing 0 vs travel 90 = 90° off
    assert perpendicular < 0.1 * aligned


def test_180_reversal_swaps_downwind(params: WindEdgeParams) -> None:
    # With a westerly (from 270°), EAST is downwind of SRC and SRC is upwind of EAST.
    src_to_east = _w(SRC, EAST, 270.0, 5.0, params)
    east_to_src = _w(EAST, SRC, 270.0, 5.0, params)
    assert src_to_east > east_to_src

    # Reverse the wind (now from the east, 90°): the roles swap exactly.
    src_to_east_rev = _w(SRC, EAST, 90.0, 5.0, params)
    east_to_src_rev = _w(EAST, SRC, 90.0, 5.0, params)
    assert east_to_src_rev > src_to_east_rev
    assert src_to_east_rev == pytest.approx(east_to_src, abs=1e-6)
    assert east_to_src_rev == pytest.approx(src_to_east, abs=1e-6)


def test_weight_monotonically_decreasing_in_angular_offset(params: WindEdgeParams) -> None:
    # Hold geometry fixed (SRC→EAST, bearing ~90°); sweep the wind's travel direction
    # away from that bearing and the weight must fall monotonically.
    prev = math.inf
    for off in range(0, 100, 10):
        # wind travels toward (90 - off); it comes FROM the opposite.
        wind_from = (90.0 - off + 180.0) % 360.0
        w = _w(SRC, EAST, wind_from, 5.0, params)
        assert w <= prev + 1e-12
        prev = w


def test_weight_monotonically_decreasing_in_distance(params: WindEdgeParams) -> None:
    prev = math.inf
    for dlon in (0.02, 0.04, 0.08, 0.12):
        w = _w(SRC, (47.53, 21.55 + dlon), 270.0, 5.0, params)
        assert w <= prev + 1e-12
        prev = w


def test_zero_wind_is_finite_zero(params: WindEdgeParams) -> None:
    w = _w(SRC, EAST, 270.0, 0.0, params)
    assert w == 0.0
    assert math.isfinite(w)


def test_calm_below_threshold_short_circuits(params: WindEdgeParams) -> None:
    # Even with a NaN bearing, a calm wind never evaluates the direction term.
    w = wind_edge_weight(SRC[0], SRC[1], EAST[0], EAST[1], float("nan"), 0.0, params)
    assert w == 0.0
    assert math.isfinite(w)


def test_beyond_cutoff_is_zero(params: WindEdgeParams) -> None:
    far = (47.53, 21.55 + 1.0)  # well beyond max_neighbour_distance_km
    assert _w(SRC, far, 270.0, 5.0, params) == 0.0


def test_speed_response_saturates(params: WindEdgeParams) -> None:
    assert speed_response(0.0, params) == 0.0
    assert 0.0 < speed_response(1.0, params) < speed_response(10.0, params) < 1.0
    assert speed_response(1e6, params) == pytest.approx(1.0, abs=1e-4)


def test_distance_decay_monotone(params: WindEdgeParams) -> None:
    assert distance_decay(0.0, params) == pytest.approx(1.0)
    assert distance_decay(1.0, params) > distance_decay(2.0, params) > 0.0


def test_params_reject_nonpositive_sigma() -> None:
    cfg = load_graph_config()
    bad = {**cfg, "wind_edges": {**cfg["wind_edges"], "sigma_angle_deg": 0.0}}
    with pytest.raises(ValueError, match="sigma_angle_deg"):
        WindEdgeParams.from_config(bad)
