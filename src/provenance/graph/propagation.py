"""Analytic propagation: what a real plume from i should do to its downwind neighbours.

Given a candidate event at station i — a rise of ``excess`` above i's own baseline —
and the wind at that hour, this predicts, for each downwind neighbour j, three
things a genuine plume must roughly satisfy:

* **when** the signal arrives — an arrival delay ``distance / effective_speed``,
  where ``effective_speed`` is the wind's component *along* the i→j bearing (a plume
  crossing the wind arrives slowly, or not at all), floored so the delay is finite;
* **how big** it arrives — an attenuated excess ``excess · g(distance)``, reusing the
  same distance decay ``g`` as the edge weight, so expectation and edge agree;
* **within what window** — the [15, 60] min horizon, bucketed to the hourly cadence.

The cadence problem, resolved explicitly (per the brief): readings are hourly, and a
plume often crosses to a near neighbour in well under an hour. Rather than
interpolate a sub-hourly value we never measured, we **widen the comparison to the
data cadence**: the expected arrival is evaluated against the neighbour's readings in
the hour(s) spanning the horizon, i.e. the hour after the event. The analytic
sub-hourly delay is still reported, for honesty and for a later higher-cadence feed.

This is an approximation of a Gaussian plume's first moment, not a dispersion model
(ADR 0007). It ranks and sizes expectations; it does not claim a concentration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from provenance.graph.edges import WindEdgeParams, distance_decay
from provenance.graph.geometry import (
    angular_difference_deg,
    haversine_km,
    initial_bearing_deg,
    wind_travel_bearing_deg,
)
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindVector


@dataclass(frozen=True, slots=True)
class PropagationParams:
    horizon_min: float
    horizon_max: float
    cadence_minutes: float
    effective_speed_floor: float
    attenuation_floor: float

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> PropagationParams:
        p = cfg["propagation"]
        return cls(
            horizon_min=float(p["horizon_minutes_min"]),
            horizon_max=float(p["horizon_minutes_max"]),
            cadence_minutes=float(p["cadence_minutes"]),
            effective_speed_floor=float(p["effective_speed_floor"]),
            attenuation_floor=float(p["attenuation_floor"]),
        )


@dataclass(frozen=True, slots=True)
class ExpectedArrival:
    """The analytic expectation at one downwind neighbour."""

    station_id: str
    distance_km: float
    bearing_deg: float
    along_wind_speed: float
    """Component of the wind velocity along the i→j bearing (m/s). Negative ⇒ upwind."""
    arrival_delay_min: float
    expected_excess: float
    attenuation: float
    within_horizon: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "distance_km": round(self.distance_km, 4),
            "bearing_deg": round(self.bearing_deg, 2),
            "along_wind_speed": round(self.along_wind_speed, 4),
            "arrival_delay_min": round(self.arrival_delay_min, 2),
            "expected_excess": round(self.expected_excess, 4),
            "attenuation": round(self.attenuation, 4),
            "within_horizon": self.within_horizon,
        }


def expected_arrival(
    source: StationPoint,
    neighbour: StationPoint,
    wind: WindVector,
    event_excess: float,
    wind_params: WindEdgeParams,
    prop_params: PropagationParams,
) -> ExpectedArrival:
    """Predict when and how strongly the event reaches ``neighbour``."""
    distance_km = haversine_km(source.lat, source.lon, neighbour.lat, neighbour.lon)
    bearing = initial_bearing_deg(source.lat, source.lon, neighbour.lat, neighbour.lon)
    travel = wind_travel_bearing_deg(wind.from_deg)
    alignment = math.cos(math.radians(angular_difference_deg(bearing, travel)))
    along = wind.speed * alignment
    effective = max(along, prop_params.effective_speed_floor)
    delay_min = (distance_km * 1000.0) / effective / 60.0

    attenuation = max(distance_decay(distance_km, wind_params), prop_params.attenuation_floor)
    expected_excess = event_excess * attenuation
    # A neighbour reached within the upper horizon corroborates at the first evaluated
    # hour; one the plume reaches faster than the lower horizon still counts (it simply
    # arrives inside that first hour). Only an arrival slower than the upper horizon
    # falls outside the evaluation window.
    within = delay_min <= prop_params.horizon_max
    return ExpectedArrival(
        station_id=neighbour.station_id,
        distance_km=distance_km,
        bearing_deg=bearing,
        along_wind_speed=along,
        arrival_delay_min=delay_min,
        expected_excess=expected_excess,
        attenuation=attenuation,
        within_horizon=within,
    )


def evaluation_hours(
    event_time: pd.Timestamp, prop_params: PropagationParams
) -> list[pd.Timestamp]:
    """The hourly timestamps over which a neighbour's actual reading is compared.

    Widened to the cadence: the horizon [15, 60] min at an hourly cadence spans the
    hour after the event, so the neighbour's reading at ``event_time + 1h`` is the
    corroboration sample. Returned as a list to keep the door open for a
    higher-cadence feed without changing callers.
    """
    step = pd.Timedelta(minutes=prop_params.cadence_minutes)
    return [pd.Timestamp(event_time) + step]
