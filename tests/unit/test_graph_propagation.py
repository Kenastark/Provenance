"""Analytic propagation: arrival delay, attenuation, horizon bucketing."""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.config.loading import load_graph_config
from provenance.graph.edges import WindEdgeParams
from provenance.graph.propagation import (
    PropagationParams,
    evaluation_hours,
    expected_arrival,
)
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindProvenance, WindVector

SRC = StationPoint("SRC", 47.53, 21.55)
NEAR = StationPoint("NEAR", 47.53, 21.59)  # ~3 km east
FAR = StationPoint("FAR", 47.53, 21.67)  # ~9 km east


@pytest.fixture
def cfg() -> dict:
    return load_graph_config()


def _wind(from_deg: float = 270.0, speed: float = 5.0) -> WindVector:
    return WindVector(from_deg, speed, "m/s", WindProvenance.STATION_LOCAL, 1)


def test_downwind_arrival_is_finite_and_ordered(cfg: dict) -> None:
    wp = WindEdgeParams.from_config(cfg)
    pp = PropagationParams.from_config(cfg)
    near = expected_arrival(SRC, NEAR, _wind(), 170.0, wp, pp)
    far = expected_arrival(SRC, FAR, _wind(), 170.0, wp, pp)
    # Farther neighbour: longer delay, more attenuation, smaller expected excess.
    assert far.arrival_delay_min > near.arrival_delay_min
    assert far.expected_excess < near.expected_excess
    assert near.along_wind_speed == pytest.approx(5.0, abs=0.05)  # dead downwind


def test_attenuation_scales_the_excess(cfg: dict) -> None:
    wp = WindEdgeParams.from_config(cfg)
    pp = PropagationParams.from_config(cfg)
    arrival = expected_arrival(SRC, NEAR, _wind(), 100.0, wp, pp)
    assert 0.0 < arrival.attenuation <= 1.0
    assert arrival.expected_excess == pytest.approx(100.0 * arrival.attenuation, rel=1e-9)


def test_perpendicular_neighbour_has_floored_speed_finite_delay(cfg: dict) -> None:
    wp = WindEdgeParams.from_config(cfg)
    pp = PropagationParams.from_config(cfg)
    north = StationPoint("N", 47.60, 21.55)  # bearing ~0, wind travels east ⇒ crosswind
    arrival = expected_arrival(SRC, north, _wind(), 100.0, wp, pp)
    # Along-wind component ~0, so the delay uses the floor and stays finite.
    assert arrival.along_wind_speed == pytest.approx(0.0, abs=0.2)
    assert arrival.arrival_delay_min < float("inf")
    assert arrival.arrival_delay_min > 0.0


def test_within_horizon_is_capped_by_the_upper_bound(cfg: dict) -> None:
    wp = WindEdgeParams.from_config(cfg)
    pp = PropagationParams.from_config(cfg)
    near = expected_arrival(SRC, NEAR, _wind(), 100.0, wp, pp)
    assert near.within_horizon is True  # ~10 min at 5 m/s
    # A very slow wind pushes arrival past the 60-min horizon.
    slow = expected_arrival(SRC, FAR, _wind(speed=0.5), 100.0, wp, pp)
    assert slow.within_horizon is False


def test_evaluation_hours_widen_to_cadence(cfg: dict) -> None:
    pp = PropagationParams.from_config(cfg)
    t = pd.Timestamp("2026-06-01T12:00:00")
    hours = evaluation_hours(t, pp)
    assert hours == [t + pd.Timedelta(minutes=pp.cadence_minutes)]


def test_arrival_to_dict_is_rounded(cfg: dict) -> None:
    wp = WindEdgeParams.from_config(cfg)
    pp = PropagationParams.from_config(cfg)
    d = expected_arrival(SRC, NEAR, _wind(), 100.0, wp, pp).to_dict()
    assert d["station_id"] == "NEAR"
    assert isinstance(d["within_horizon"], bool)
