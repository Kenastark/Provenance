"""PopulationExposure from the aggregated GTFS transit-corridor layer (§7.8).

Risk = Trust × SeverityVsThreshold × PopulationExposure. Phase 2 stubbed the
exposure factor at a permanent 1.0 and flagged it as stubbed. This module replaces
that stub with a value **computed per station from a GTFS static bundle**: it is a
proxy for how many people a station's readings speak for, so a broken reading in a
busy transit corridor outranks the same fault at a rural background site.

The proxy is transit *service intensity*: every GTFS stop within
``corridor_radius_m`` of a station contributes the number of distinct routes that
serve it, and the per-station intensities are min-max normalised across the network
into a bounded multiplier in ``[floor, ceil]``. The band edges and the corridor
width are modelling choices (they live in ``graph.yaml``); the intensity counts come
from the file, so no exposure figure is a data-derived constant baked into code
(standing rule 1).

A station with no coordinate, or a network with no service anywhere, keeps exposure
at the neutral 1.0 and is reported as stubbed — graceful degradation (standing
rule 6), and the reason the ``population_exposure_stubbed`` flag is no longer
permanently true.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from provenance.config.loading import load_graph_config

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres — the corridor is a real walking catchment."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True, slots=True)
class ExposureParams:
    """The four modelling choices behind the exposure multiplier (from ``graph.yaml``)."""

    corridor_radius_m: float
    floor: float
    ceil: float
    min_service: float

    @classmethod
    def from_config(cls, cfg: dict[str, Any] | None = None) -> ExposureParams:
        cfg = cfg or load_graph_config()
        e = cfg.get("exposure", {})
        return cls(
            corridor_radius_m=float(e.get("corridor_radius_m", 500.0)),
            floor=float(e.get("floor", 0.6)),
            ceil=float(e.get("ceil", 1.6)),
            min_service=float(e.get("min_service", 1.0)),
        )


@dataclass(frozen=True, slots=True)
class ExposureLayer:
    """The aggregated transit-corridor layer: a per-station exposure multiplier.

    ``exposure`` maps a station id to its multiplier in ``[floor, ceil]``. ``service``
    carries the raw route-weighted stop count each multiplier was normalised from, so
    the figure is auditable rather than a bare number. ``measured`` lists the stations
    whose exposure is genuinely computed (service ≥ ``min_service``); every other
    station is neutral 1.0 and reported as stubbed.
    """

    exposure: dict[str, float]
    service: dict[str, float] = field(default_factory=dict)
    measured: frozenset[str] = frozenset()

    def factor_for(self, station_id: str) -> float:
        return self.exposure.get(station_id, 1.0)

    def is_measured(self, station_id: str) -> bool:
        return station_id in self.measured


def station_service_intensity(
    stops: pd.DataFrame,
    points: dict[str, tuple[float, float]],
    params: ExposureParams,
) -> dict[str, float]:
    """Route-weighted count of GTFS stops in each station's corridor.

    ``stops`` needs ``stop_lat``, ``stop_lon`` and ``n_routes`` (distinct routes
    serving the stop); ``points`` maps station id → (lat, lon). A station with no
    coordinate is omitted (it cannot have a corridor), never assigned zero — absence
    is not a measurement.
    """
    intensity: dict[str, float] = {}
    if stops.empty:
        return dict.fromkeys(points, 0.0)
    lats = stops["stop_lat"].to_numpy(dtype=float)
    lons = stops["stop_lon"].to_numpy(dtype=float)
    weights = stops["n_routes"].to_numpy(dtype=float)
    for sid, (slat, slon) in points.items():
        total = 0.0
        for lat, lon, w in zip(lats, lons, weights, strict=True):
            if _haversine_m(slat, slon, lat, lon) <= params.corridor_radius_m:
                total += w
        intensity[sid] = total
    return intensity


def build_exposure_layer(
    stops: pd.DataFrame,
    points: dict[str, tuple[float, float]],
    *,
    cfg: dict[str, Any] | None = None,
) -> ExposureLayer:
    """Aggregate a GTFS stop table into a per-station exposure multiplier.

    Deterministic: the same stops and coordinates always yield the same layer. When
    every station has the same intensity (a flat network) the band does not collapse —
    every station maps to the neutral 1.0 — because a normalisation with no spread
    should not manufacture one.
    """
    params = ExposureParams.from_config(cfg)
    intensity = station_service_intensity(stops, points, params)
    measured = {sid for sid, s in intensity.items() if s >= params.min_service}

    served = {sid: s for sid, s in intensity.items() if sid in measured}
    exposure: dict[str, float] = dict.fromkeys(points, 1.0)
    if served:
        lo = min(served.values())
        hi = max(served.values())
        span = hi - lo
        for sid, s in served.items():
            if span <= 0:
                exposure[sid] = 1.0
            else:
                frac = (s - lo) / span
                exposure[sid] = round(params.floor + (params.ceil - params.floor) * frac, 6)
    return ExposureLayer(
        exposure=exposure,
        service={sid: round(s, 6) for sid, s in intensity.items()},
        measured=frozenset(measured),
    )
