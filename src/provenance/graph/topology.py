"""The network's node geometry: real where we have it, honest placeholder where we don't.

Env stations are the real thing — their coordinates are the ones parsed from the
Green Sentinel export (or the fixture sidecar), never invented. The weather node is
a *computed* fact: the centroid of the env stations, i.e. one city-level node.

The other two node types are the awkward, honest part. Traffic counters (Enclod)
and bus stops (GTFS) have **unconfirmed schemas** — their adapters fail loudly
rather than parse (ADR 0003) — so their real coordinates are not available yet.
Until they are, they are placed **deterministically over the envelope of the real
env stations** from a seeded RNG, and the whole set is stamped
``synthetic-provisional``. This is not passed off as Enclod/GTFS data: it gives the
graph the right *shape* (a bounded set of the right node types in roughly the right
place) for the map and the message-passing structure, and no more. When the feeds
are confirmed, this module is where the generated points are swapped for read ones,
with no change to the snapshot builder or the adjudicator.

Bus stops are the one place §16 critique 6 bites: a real GTFS feed has hundreds of
stops, and message-passing them at full resolution is both meaningless and slow. So
raw stops are **aggregated to corridors** — a bounded number of nodes — here, before
they ever reach the graph, and the bound is asserted by a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from provenance.graph.snapshot import NODE_ID, NodeType


@dataclass(frozen=True, slots=True)
class StationPoint:
    """An env station's id and coordinates (the only real coordinates in the graph)."""

    station_id: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class TopologyParams:
    traffic_counters: int
    bus_stops_raw: int
    bus_corridor_max: int
    road_adjacency_k: int
    seed: int

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> TopologyParams:
        t = cfg["topology"]
        return cls(
            traffic_counters=int(t["traffic_counters"]),
            bus_stops_raw=int(t["bus_stops_raw"]),
            bus_corridor_max=int(t["bus_corridor_max"]),
            road_adjacency_k=int(t["road_adjacency_k"]),
            seed=int(t["seed"]),
        )


def _envelope(points: list[StationPoint]) -> tuple[float, float, float, float]:
    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    return min(lats), max(lats), min(lons), max(lons)


def env_station_nodes(points: list[StationPoint]) -> pd.DataFrame:
    """The EnvStation node table, indexed by station id. Real coordinates only."""
    frame = pd.DataFrame(
        {
            NODE_ID: [p.station_id for p in points],
            "lat": [p.lat for p in points],
            "lon": [p.lon for p in points],
            "kind": NodeType.ENV_STATION.value,
        }
    )
    return frame.set_index(NODE_ID).sort_index()


def weather_node(points: list[StationPoint]) -> pd.DataFrame:
    """A single city-level WeatherNode at the centroid of the env stations (computed)."""
    lat = float(np.mean([p.lat for p in points]))
    lon = float(np.mean([p.lon for p in points]))
    frame = pd.DataFrame(
        {
            NODE_ID: ["WEATHER-CITY"],
            "lat": [lat],
            "lon": [lon],
            "kind": NodeType.WEATHER_NODE.value,
        }
    )
    return frame.set_index(NODE_ID)


def traffic_counter_nodes(points: list[StationPoint], params: TopologyParams) -> pd.DataFrame:
    """TrafficCounter nodes, synthetic-provisional, placed over the station envelope.

    Deterministic from ``params.seed``: counter *n* always lands on the same point.
    """
    lat_min, lat_max, lon_min, lon_max = _envelope(points)
    rng = np.random.default_rng(params.seed)
    n = params.traffic_counters
    lats = rng.uniform(lat_min, lat_max, size=n)
    lons = rng.uniform(lon_min, lon_max, size=n)
    frame = pd.DataFrame(
        {
            NODE_ID: [f"TC-{i:03d}" for i in range(n)],
            "lat": np.round(lats, 6),
            "lon": np.round(lons, 6),
            "kind": NodeType.TRAFFIC_COUNTER.value,
            "provenance": "synthetic-provisional",
        }
    )
    return frame.set_index(NODE_ID).sort_index()


def bus_corridor_nodes(points: list[StationPoint], params: TopologyParams) -> pd.DataFrame:
    """BusStop nodes AGGREGATED to corridors — a bounded node count, never raw stops.

    Raw stops are generated over the envelope, then binned into a square grid whose
    side is chosen so the number of cells never exceeds ``bus_corridor_max``. Each
    non-empty cell becomes one corridor node at the mean position of its stops,
    carrying the count it aggregates. The result has AT MOST ``bus_corridor_max``
    nodes regardless of how many raw stops there were (§16 critique 6).
    """
    lat_min, lat_max, lon_min, lon_max = _envelope(points)
    rng = np.random.default_rng(params.seed + 1)
    raw_lats = rng.uniform(lat_min, lat_max, size=params.bus_stops_raw)
    raw_lons = rng.uniform(lon_min, lon_max, size=params.bus_stops_raw)

    # Largest square grid whose cell count does not exceed the corridor bound.
    side = max(1, int(np.floor(np.sqrt(params.bus_corridor_max))))
    lat_edges = np.linspace(lat_min, lat_max, side + 1)
    lon_edges = np.linspace(lon_min, lon_max, side + 1)
    lat_bin = np.clip(np.digitize(raw_lats, lat_edges) - 1, 0, side - 1)
    lon_bin = np.clip(np.digitize(raw_lons, lon_edges) - 1, 0, side - 1)

    buckets: dict[tuple[int, int], list[int]] = {}
    for idx, (a, b) in enumerate(zip(lat_bin.tolist(), lon_bin.tolist(), strict=True)):
        buckets.setdefault((a, b), []).append(idx)

    rows: list[dict[str, Any]] = []
    for (a, b), members in sorted(buckets.items()):
        rows.append(
            {
                NODE_ID: f"BC-{a:02d}-{b:02d}",
                "lat": round(float(raw_lats[members].mean()), 6),
                "lon": round(float(raw_lons[members].mean()), 6),
                "kind": NodeType.BUS_STOP.value,
                "n_stops": len(members),
                "provenance": "synthetic-provisional",
            }
        )
    frame = pd.DataFrame(rows)
    return frame.set_index(NODE_ID).sort_index()
