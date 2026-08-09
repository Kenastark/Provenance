"""Turn the canonical readings + graph geometry into the HST-GAT's temporal tensors.

The model reconstructs one propagating pollutant (the *target parameter*, PM10 by
default) at every EnvStation and every hour from its wind-weighted neighbours. This
module assembles exactly the tensors that needs and nothing it does not:

* ``target``/``observed`` — the standardised target value per (hour, station) and a
  mask of where a real reading exists (structural absence is not invented, standing
  rule 2);
* per-hour, per-station wind features, real where the network measured wind and zero
  where it is calm/unmeasured (never a fabricated calm);
* five typed relations, every one oriented so **EnvStation is the destination**, so a
  station's update aggregates messages across all edge types (§6.4). The wind relation
  additionally carries a per-hour weight that becomes the attention bias.

The auxiliary source types (TrafficCounter, BusStop, WeatherNode) carry no confirmed
time-varying measurements yet, so the model represents them with learned type
embeddings rather than invented features — honest placeholders, marked as such in the
model card. Determinism: everything is built in the snapshot's stable id order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor

from provenance.graph.build import build_snapshot
from provenance.graph.edges import WindEdgeParams, speed_response, wind_edge_weight
from provenance.graph.snapshot import EDGE_DST, EDGE_SRC, EdgeType, NodeType
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.schema import canonical as C

WIND_FEATURE_DIM = 3  # [sin(from), cos(from), saturated-speed]


@dataclass(frozen=True, slots=True)
class Relation:
    """One typed relation, oriented with EnvStation as the destination.

    ``edge_index`` is ``[2, E]`` with row 0 the source index (in the source type's node
    space) and row 1 the destination EnvStation index. ``static_weight`` is the
    edge's time-invariant kernel weight; ``wind_weight`` is ``[T, E]`` and present only
    for the wind-conditioned relation (its attention bias), ``None`` otherwise.
    """

    edge_type: EdgeType
    src_type: NodeType
    n_src: int
    edge_index: Tensor
    static_weight: Tensor
    wind_weight: Tensor | None = None


@dataclass(frozen=True, slots=True)
class TemporalGraphBatch:
    """Everything one training/forecast pass over a corpus needs, as tensors.

    ``target`` and ``observed`` are ``[T, n_env]``; ``env_wind`` is ``[T, n_env, 3]``;
    ``weather_wind`` is ``[T, 3]``. ``mean``/``std`` are the target's standardisation
    constants, kept so a prediction can be mapped back to a physical value.
    """

    env_ids: list[str]
    times: list[pd.Timestamp]
    target: Tensor
    observed: Tensor
    env_wind: Tensor
    weather_wind: Tensor
    relations: dict[EdgeType, Relation]
    mean: float
    std: float
    target_parameter: str
    meta: dict[str, object] = field(default_factory=dict)

    @property
    def n_env(self) -> int:
        return len(self.env_ids)

    @property
    def n_times(self) -> int:
        return len(self.times)


def truncate_batch(batch: TemporalGraphBatch, n_times: int) -> TemporalGraphBatch:
    """A view of ``batch`` restricted to its first ``n_times`` hours.

    Only the time-varying tensors are sliced (target/observed/wind features and the
    wind relation's per-hour weight); the static topology is shared. Used to keep the
    overfit-a-tiny-batch gate sub-second — the temporal forward loop is O(hours).
    """
    n_times = min(n_times, batch.n_times)
    relations = dict(batch.relations)
    wind_rel = relations.get(EdgeType.WIND_CONDITIONED)
    if wind_rel is not None and wind_rel.wind_weight is not None:
        relations[EdgeType.WIND_CONDITIONED] = Relation(
            edge_type=wind_rel.edge_type,
            src_type=wind_rel.src_type,
            n_src=wind_rel.n_src,
            edge_index=wind_rel.edge_index,
            static_weight=wind_rel.static_weight,
            wind_weight=wind_rel.wind_weight[:n_times],
        )
    return TemporalGraphBatch(
        env_ids=batch.env_ids,
        times=batch.times[:n_times],
        target=batch.target[:n_times],
        observed=batch.observed[:n_times],
        env_wind=batch.env_wind[:n_times],
        weather_wind=batch.weather_wind[:n_times],
        relations=relations,
        mean=batch.mean,
        std=batch.std,
        target_parameter=batch.target_parameter,
        meta=dict(batch.meta),
    )


def _wind_features(
    wind: WindField, station_id: str, ts: pd.Timestamp, params: WindEdgeParams
) -> tuple[float, float, float]:
    vec = wind.at(ts, station_id)
    if vec is None or vec.speed < params.min_wind_speed:
        return (0.0, 0.0, 0.0)
    rad = math.radians(vec.from_deg)
    return (math.sin(rad), math.cos(rad), speed_response(vec.speed, params))


def _reverse_relation(
    edges: pd.DataFrame,
    src_ids: list[str],
    env_index: dict[str, int],
    edge_type: EdgeType,
    src_type: NodeType,
) -> Relation:
    """Build an ``aux -> EnvStation`` relation from an ``EnvStation -> aux`` edge table.

    The snapshot stores road/transit edges as env→aux; the model wants messages
    flowing *into* env, so the orientation is reversed here (env stays the destination).
    """
    src_pos = {sid: i for i, sid in enumerate(src_ids)}
    rows: list[int] = []
    cols: list[int] = []
    weights: list[float] = []
    if not edges.empty:
        for _, e in edges.iterrows():
            env_id = str(e[EDGE_SRC])  # env is the source in the stored env→aux table
            aux_id = str(e[EDGE_DST])
            if env_id not in env_index or aux_id not in src_pos:
                continue
            rows.append(src_pos[aux_id])  # source = aux
            cols.append(env_index[env_id])  # destination = env
            weights.append(float(e["weight"]))
    return Relation(
        edge_type=edge_type,
        src_type=src_type,
        n_src=len(src_ids),
        edge_index=torch.tensor([rows, cols], dtype=torch.long),
        static_weight=torch.tensor(weights, dtype=torch.float32),
    )


def build_batch(
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    *,
    target_parameter: str = "PM10",
    mean: float | None = None,
    std: float | None = None,
) -> TemporalGraphBatch:
    """Assemble a :class:`TemporalGraphBatch` for ``target_parameter`` from a corpus.

    The target parameter is used only if the frame carries it (else a ``ValueError``,
    never an invented column). Env stations are the mapped points that measure it.

    ``mean``/``std`` override the standardisation constants — pass the *trained* model's
    constants when tensorising fresh readings for a forecast, so the inputs are scaled
    the way the model expects; leave ``None`` at training time to compute them here.
    """
    present = set(frame[C.PARAMETER].astype(str).unique())
    if target_parameter not in present:
        raise ValueError(
            f"Target parameter {target_parameter!r} is not in the corpus (has {sorted(present)}); "
            "refusing to invent it (standing rule 2)."
        )
    wind_params = WindEdgeParams.from_config(cfg)

    tgt = frame[frame[C.PARAMETER] == target_parameter]
    carriers = set(tgt[C.STATION_ID].astype(str).unique())
    env_points = [p for p in sorted(points, key=lambda q: q.station_id) if p.station_id in carriers]
    env_ids = [p.station_id for p in env_points]
    if not env_ids:
        raise ValueError(f"No mapped station carries {target_parameter!r}.")
    env_index = {sid: i for i, sid in enumerate(env_ids)}

    times = sorted(pd.Timestamp(t) for t in tgt[C.TIMESTAMP].unique())
    t_index = {t: i for i, t in enumerate(times)}
    n_t, n_env = len(times), len(env_ids)

    # Target matrix + observed mask, in (time, station) order.
    values = np.full((n_t, n_env), np.nan, dtype="float64")
    for _, r in tgt.iterrows():
        sid = str(r[C.STATION_ID])
        ts = pd.Timestamp(r[C.TIMESTAMP])
        if sid in env_index and ts in t_index:
            values[t_index[ts], env_index[sid]] = float(r[C.VALUE])
    observed = ~np.isnan(values)
    if mean is None:
        mean = float(np.nanmean(values)) if observed.any() else 0.0
    if std is None:
        std = float(np.nanstd(values)) if observed.any() else 1.0
    std = std if std > 1e-8 else 1.0
    standardised = np.where(observed, (values - mean) / std, 0.0)

    # Per-(time, station) wind features and the city (weather-node) wind.
    env_wind = np.zeros((n_t, n_env, WIND_FEATURE_DIM), dtype="float32")
    weather_wind = np.zeros((n_t, WIND_FEATURE_DIM), dtype="float32")
    for ti, ts in enumerate(times):
        for si, sid in enumerate(env_ids):
            env_wind[ti, si] = _wind_features(wind, sid, ts, wind_params)
        city = wind.city_at(ts)
        if city is not None and city.speed >= wind_params.min_wind_speed:
            rad = math.radians(city.from_deg)
            weather_wind[ti] = (
                math.sin(rad),
                math.cos(rad),
                speed_response(city.speed, wind_params),
            )

    # Static topology from a reference snapshot; wind weights recomputed per hour.
    snap = build_snapshot(env_points, wind, times[0], cfg)
    relations = _build_relations(snap, env_points, env_index, times, wind, wind_params)

    return TemporalGraphBatch(
        env_ids=env_ids,
        times=times,
        target=torch.tensor(standardised, dtype=torch.float32),
        observed=torch.tensor(observed, dtype=torch.bool),
        env_wind=torch.tensor(env_wind, dtype=torch.float32),
        weather_wind=torch.tensor(weather_wind, dtype=torch.float32),
        relations=relations,
        mean=mean,
        std=std,
        target_parameter=target_parameter,
        meta={"n_env": n_env, "n_times": n_t},
    )


def _build_relations(
    snap: object,
    env_points: list[StationPoint],
    env_index: dict[str, int],
    times: list[pd.Timestamp],
    wind: WindField,
    wind_params: WindEdgeParams,
) -> dict[EdgeType, Relation]:
    from provenance.graph.snapshot import GraphSnapshot

    assert isinstance(snap, GraphSnapshot)
    relations: dict[EdgeType, Relation] = {}

    # env -> env candidate pairs (from the spatial table; same pair set the wind edge uses).
    spatial = snap.edge_table(EdgeType.SPATIAL_PROXIMITY)
    rows: list[int] = []
    cols: list[int] = []
    spat_w: list[float] = []
    pairs: list[tuple[str, str]] = []
    if not spatial.empty:
        for _, e in spatial.iterrows():
            s, d = str(e[EDGE_SRC]), str(e[EDGE_DST])
            if s in env_index and d in env_index:
                rows.append(env_index[s])
                cols.append(env_index[d])
                spat_w.append(float(e["weight"]))
                pairs.append((s, d))
    env_edge_index = torch.tensor([rows, cols], dtype=torch.long)
    relations[EdgeType.SPATIAL_PROXIMITY] = Relation(
        edge_type=EdgeType.SPATIAL_PROXIMITY,
        src_type=NodeType.ENV_STATION,
        n_src=len(env_index),
        edge_index=env_edge_index,
        static_weight=torch.tensor(spat_w, dtype=torch.float32),
    )

    # Wind: same env->env pairs, weight recomputed each hour → [T, E].
    by_id = {p.station_id: p for p in env_points}
    n_e = len(pairs)
    wind_w = np.zeros((len(times), n_e), dtype="float32")
    for ti, ts in enumerate(times):
        for ei, (s, d) in enumerate(pairs):
            vec = wind.at(ts, s)
            if vec is None:
                continue
            a, b = by_id[s], by_id[d]
            wind_w[ti, ei] = wind_edge_weight(
                a.lat, a.lon, b.lat, b.lon, vec.from_deg, vec.speed, wind_params
            )
    relations[EdgeType.WIND_CONDITIONED] = Relation(
        edge_type=EdgeType.WIND_CONDITIONED,
        src_type=NodeType.ENV_STATION,
        n_src=len(env_index),
        edge_index=env_edge_index,
        static_weight=torch.tensor(spat_w, dtype=torch.float32),
        wind_weight=torch.tensor(wind_w, dtype=torch.float32),
    )

    # Weather node -> env (broadcast, weight 1).
    weather = snap.node_table(NodeType.WEATHER_NODE)
    w_rows: list[int] = []
    w_cols: list[int] = []
    w_wt: list[float] = []
    w_edges = snap.edge_table(EdgeType.WEATHER_INFLUENCE)
    if not w_edges.empty:
        for _, e in w_edges.iterrows():
            d = str(e[EDGE_DST])
            if d in env_index:
                w_rows.append(0)  # single weather node
                w_cols.append(env_index[d])
                w_wt.append(float(e["weight"]))
    relations[EdgeType.WEATHER_INFLUENCE] = Relation(
        edge_type=EdgeType.WEATHER_INFLUENCE,
        src_type=NodeType.WEATHER_NODE,
        n_src=max(len(weather), 1),
        edge_index=torch.tensor([w_rows, w_cols], dtype=torch.long),
        static_weight=torch.tensor(w_wt, dtype=torch.float32),
    )

    # Auxiliary types, reversed so they flow into env (placeholder src features).
    traffic_ids = [str(x) for x in snap.node_table(NodeType.TRAFFIC_COUNTER).index]
    corridor_ids = [str(x) for x in snap.node_table(NodeType.BUS_STOP).index]
    relations[EdgeType.ROAD_ADJACENCY] = _reverse_relation(
        snap.edge_table(EdgeType.ROAD_ADJACENCY),
        traffic_ids,
        env_index,
        EdgeType.ROAD_ADJACENCY,
        NodeType.TRAFFIC_COUNTER,
    )
    relations[EdgeType.TRANSIT_CORRIDOR] = _reverse_relation(
        snap.edge_table(EdgeType.TRANSIT_CORRIDOR),
        corridor_ids,
        env_index,
        EdgeType.TRANSIT_CORRIDOR,
        NodeType.BUS_STOP,
    )
    return relations
