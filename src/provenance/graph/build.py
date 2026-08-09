"""Assemble a :class:`GraphSnapshot` at a timestamp from stations, wind, and config.

The static edge kernels (spatial proximity, road adjacency, transit corridors,
weather broadcast) do not depend on ``t`` and could be cached; only
``wind_conditioned`` is recomputed per timestep. They are built together here so a
snapshot is one self-contained object, and because the whole build is comfortably
under the 100 ms budget for the real network — the edge sets are bounded by
construction (env-env, env-to-k-traffic, env-corridors, weather-to-env).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from provenance.graph import topology as topo
from provenance.graph.edges import WindEdgeParams, inverse_distance_weight, wind_edge_weight
from provenance.graph.geometry import haversine_km, initial_bearing_deg
from provenance.graph.snapshot import (
    EDGE_DST,
    EDGE_SRC,
    EDGE_WEIGHT,
    EdgeType,
    GraphSnapshot,
    NodeType,
)
from provenance.graph.topology import StationPoint, TopologyParams
from provenance.graph.wind import WindField, WindProvenance


def _spatial_edges(points: list[StationPoint], params: WindEdgeParams) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for a in points:
        for b in points:
            if a.station_id == b.station_id:
                continue
            dist = haversine_km(a.lat, a.lon, b.lat, b.lon)
            if dist > params.max_neighbour_distance_km:
                continue
            rows.append(
                {
                    EDGE_SRC: a.station_id,
                    EDGE_DST: b.station_id,
                    EDGE_WEIGHT: round(inverse_distance_weight(dist), 6),
                    "distance_km": round(dist, 6),
                }
            )
    return _sorted_edges(rows)


def _wind_edges(
    points: list[StationPoint],
    wind: WindField,
    at: pd.Timestamp,
    params: WindEdgeParams,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for a in points:
        vec = wind.at(at, a.station_id)
        for b in points:
            if a.station_id == b.station_id:
                continue
            dist = haversine_km(a.lat, a.lon, b.lat, b.lon)
            if dist > params.max_neighbour_distance_km:
                continue
            if vec is None:
                weight = 0.0
                provenance = WindProvenance.UNAVAILABLE.value
            else:
                weight = wind_edge_weight(
                    a.lat, a.lon, b.lat, b.lon, vec.from_deg, vec.speed, params
                )
                provenance = vec.provenance.value
            rows.append(
                {
                    EDGE_SRC: a.station_id,
                    EDGE_DST: b.station_id,
                    EDGE_WEIGHT: round(float(weight), 6),
                    "distance_km": round(dist, 6),
                    "bearing_deg": round(initial_bearing_deg(a.lat, a.lon, b.lat, b.lon), 4),
                    "wind_provenance": provenance,
                }
            )
    return _sorted_edges(rows)


def _road_adjacency_edges(
    points: list[StationPoint], traffic: pd.DataFrame, k: int
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for a in points:
        dists = [
            (tid, haversine_km(a.lat, a.lon, float(row["lat"]), float(row["lon"])))
            for tid, row in traffic.iterrows()
        ]
        dists.sort(key=lambda item: (item[1], item[0]))
        for tid, dist in dists[:k]:
            rows.append(
                {
                    EDGE_SRC: a.station_id,
                    EDGE_DST: str(tid),
                    EDGE_WEIGHT: round(inverse_distance_weight(dist), 6),
                    "distance_km": round(dist, 6),
                }
            )
    return _sorted_edges(rows)


def _transit_corridor_edges(
    points: list[StationPoint], corridors: pd.DataFrame, params: WindEdgeParams
) -> pd.DataFrame:
    """Env→corridor edges, exposure-weighted by the stops the corridor aggregates."""
    rows: list[dict[str, Any]] = []
    for a in points:
        for cid, row in corridors.iterrows():
            dist = haversine_km(a.lat, a.lon, float(row["lat"]), float(row["lon"]))
            if dist > params.max_neighbour_distance_km:
                continue
            exposure = inverse_distance_weight(dist) * float(row.get("n_stops", 1))
            rows.append(
                {
                    EDGE_SRC: a.station_id,
                    EDGE_DST: str(cid),
                    EDGE_WEIGHT: round(exposure, 6),
                    "distance_km": round(dist, 6),
                    "n_stops": int(row.get("n_stops", 1)),
                }
            )
    return _sorted_edges(rows)


def _weather_influence_edges(points: list[StationPoint], weather: pd.DataFrame) -> pd.DataFrame:
    """The city weather node broadcasts to every env station (weight 1.0)."""
    weather_id = str(weather.index[0])
    rows = [{EDGE_SRC: weather_id, EDGE_DST: p.station_id, EDGE_WEIGHT: 1.0} for p in points]
    return _sorted_edges(rows)


def _sorted_edges(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values([EDGE_SRC, EDGE_DST], kind="stable").reset_index(drop=True)


def build_snapshot(
    points: list[StationPoint],
    wind: WindField,
    at: pd.Timestamp,
    cfg: dict[str, Any],
) -> GraphSnapshot:
    """Build the full heterogeneous snapshot at ``at``.

    Pure in ``(points, wind at ``at``, cfg)``: the same inputs always produce the
    same tables, which is the graph invariant the tests pin.
    """
    at = pd.Timestamp(at)
    wind_params = WindEdgeParams.from_config(cfg)
    topo_params = TopologyParams.from_config(cfg)

    env = topo.env_station_nodes(points)
    traffic = topo.traffic_counter_nodes(points, topo_params)
    corridors = topo.bus_corridor_nodes(points, topo_params)
    weather = topo.weather_node(points)

    nodes = {
        NodeType.ENV_STATION: env,
        NodeType.TRAFFIC_COUNTER: traffic,
        NodeType.BUS_STOP: corridors,
        NodeType.WEATHER_NODE: weather,
    }
    edges = {
        EdgeType.SPATIAL_PROXIMITY: _spatial_edges(points, wind_params),
        EdgeType.WIND_CONDITIONED: _wind_edges(points, wind, at, wind_params),
        EdgeType.ROAD_ADJACENCY: _road_adjacency_edges(
            points, traffic, topo_params.road_adjacency_k
        ),
        EdgeType.TRANSIT_CORRIDOR: _transit_corridor_edges(points, corridors, wind_params),
        EdgeType.WEATHER_INFLUENCE: _weather_influence_edges(points, weather),
    }
    vec = wind.city_at(at)
    meta: dict[str, Any] = {
        "wind_available": vec is not None,
        "wind_from_deg": None if vec is None else round(vec.from_deg, 4),
        "wind_speed": None if vec is None else round(vec.speed, 4),
        "wind_speed_unit": wind.speed_unit,
    }
    return GraphSnapshot(timestamp=at, nodes=nodes, edges=edges, meta=meta)


def station_points_from_metadata(meta: dict[str, Any]) -> list[StationPoint]:
    """Turn a ``{station_id: StationLocation}`` map into station points, sorted by id.

    Stations without a coordinate are dropped (they cannot sit in a geometric graph);
    the caller already surfaces "not mapped" coverage facts elsewhere.
    """
    points: list[StationPoint] = []
    for station_id in sorted(meta):
        loc = meta[station_id]
        lat = getattr(loc, "lat", None)
        lon = getattr(loc, "lon", None)
        if lat is None or lon is None:
            continue
        points.append(StationPoint(station_id=station_id, lat=float(lat), lon=float(lon)))
    return points
