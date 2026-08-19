"""The wind-conditioned edge weight and the static edge kernels.

The dynamic weight is the phase's physics, and it is deliberately simple::

    w(i, j, t) = exp(-Δθ / sigma_angle) · f(|wind_speed(t)|) · g(distance(i, j))

* ``exp(-Δθ / sigma_angle)`` — the dispersion-cone term. Δθ is the wrapped gap between
  the i→j bearing and the direction the air is travelling (see
  :func:`geometry.wind_travel_bearing_deg`). Maximum (1.0) when j is dead downwind of
  i; ~0 when j is off-axis or upwind. sigma_angle is the cone half-width from config.
* ``f`` — a saturating response to wind speed, ``s / (s + s_half)``: monotone up,
  → 1 as ``s → ∞``, and importantly ``f(0) = 0`` so a calm timestep collapses every
  wind edge to zero **without** ever evaluating the (undefined) calm-wind direction.
* ``g`` — an exponential decay with distance, ``exp(-d / d_decay)``, hard-cut to 0
  beyond ``max_neighbour_distance_km`` so the edge set stays local and bounded.

This is a lightweight, differentiable approximation of a Gaussian plume's footprint,
**not** an atmospheric dispersion model — the honesty is load-bearing (ADR 0007,
§16 critique 3). It exists to rank which neighbours a plume should reach first and
by how much, cheaply and deterministically, not to predict a concentration field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from provenance.graph.geometry import (
    angular_difference_deg,
    haversine_km,
    initial_bearing_deg,
    wind_travel_bearing_deg,
)


@dataclass(frozen=True, slots=True)
class WindEdgeParams:
    """The parameters of :func:`wind_edge_weight`, read from ``config/graph.yaml``."""

    sigma_angle_deg: float
    wind_speed_half_saturation: float
    distance_decay_km: float
    max_neighbour_distance_km: float
    min_wind_speed: float

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> WindEdgeParams:
        we = cfg["wind_edges"]
        params = cls(
            sigma_angle_deg=float(we["sigma_angle_deg"]),
            wind_speed_half_saturation=float(we["wind_speed_half_saturation"]),
            distance_decay_km=float(we["distance_decay_km"]),
            max_neighbour_distance_km=float(we["max_neighbour_distance_km"]),
            min_wind_speed=float(we["min_wind_speed"]),
        )
        if params.sigma_angle_deg <= 0:
            raise ValueError("sigma_angle_deg must be > 0 (it is a divisor in the cone term).")
        if params.wind_speed_half_saturation <= 0:
            raise ValueError("wind_speed_half_saturation must be > 0.")
        if params.distance_decay_km <= 0:
            raise ValueError("distance_decay_km must be > 0.")
        return params


def speed_response(speed: float, params: WindEdgeParams) -> float:
    """``f(s) = s / (s + s_half)`` — saturating, monotone increasing, ``f(0) = 0``."""
    s = max(0.0, speed)
    return s / (s + params.wind_speed_half_saturation)


def distance_decay(distance_km: float, params: WindEdgeParams) -> float:
    """``g(d) = exp(-d / d_decay)`` beyond a hard cutoff of 0. Monotone decreasing."""
    if distance_km > params.max_neighbour_distance_km:
        return 0.0
    return math.exp(-distance_km / params.distance_decay_km)


def direction_response(
    bearing_ij_deg: float, wind_from_deg: float, params: WindEdgeParams
) -> float:
    """``exp(-Δθ / sigma_angle)`` — the dispersion-cone term. Max at dead-downwind alignment."""
    travel = wind_travel_bearing_deg(wind_from_deg)
    delta = angular_difference_deg(bearing_ij_deg, travel)
    return math.exp(-delta / params.sigma_angle_deg)


def wind_edge_weight(
    lat_i: float,
    lon_i: float,
    lat_j: float,
    lon_j: float,
    wind_from_deg: float,
    wind_speed: float,
    params: WindEdgeParams,
) -> float:
    """Directed weight of the i→j wind edge: how strongly a plume at i reaches j now.

    A pure function of geometry, the wind at t, and config — the graph invariant the
    tests pin (recompute at t is reproducible from those three inputs alone).

    Calm short-circuit: at ``wind_speed < min_wind_speed`` the weight is 0 and the
    direction term is never evaluated, so a zero-wind timestep is degenerate but
    finite (no NaN from an undefined calm bearing, no division by zero).
    """
    if wind_speed < params.min_wind_speed:
        return 0.0
    distance_km = haversine_km(lat_i, lon_i, lat_j, lon_j)
    g = distance_decay(distance_km, params)
    if g == 0.0:
        return 0.0
    bearing = initial_bearing_deg(lat_i, lon_i, lat_j, lon_j)
    d = direction_response(bearing, wind_from_deg, params)
    f = speed_response(wind_speed, params)
    return d * f * g


def inverse_distance_weight(distance_km: float, *, epsilon_km: float = 0.05) -> float:
    """Static spatial weight ``1 / (d + ε)``. Monotone decreasing; finite at d = 0."""
    return 1.0 / (distance_km + epsilon_km)
