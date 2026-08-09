"""Materialise a :class:`GraphSnapshot` as a PyTorch Geometric ``HeteroData``.

This is the phase-6 backing the phase-4 snapshot promised (see
``graph/snapshot.py``): the numpy/pandas node and edge tables are the stable
interface, and this module turns one snapshot into tensors **without any caller of
``node_table`` / ``edge_table`` changing**. ``GraphSnapshot.to_hetero_data()`` calls
into here through a lazy import, so the rest of the pipeline (audit, trust, the
statistics layers) still imports and runs on a machine with no torch installed.

Determinism (standing rule 8): nodes are indexed in the snapshot's own stable node-id
order and edges are emitted in the snapshot's sorted ``(src, dst)`` order, so two
builds over the same snapshot produce byte-identical tensors. Every numeric column is
finite by snapshot construction, so the resulting tensors carry no NaN/inf.

Honesty (standing rule 2): the auxiliary node types (TrafficCounter, BusStop,
WeatherNode) carry no confirmed time-varying features yet — Enclod and GTFS are
unconfirmed (ADR 0003) — so their node tensors are positional placeholders, and the
model that consumes them treats their contribution as structural, not as measured
signal. Nothing here invents a feature the tables do not carry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from provenance.graph.snapshot import (
    EDGE_DST,
    EDGE_SRC,
    EDGE_WEIGHT,
    EdgeType,
    GraphSnapshot,
    NodeType,
)

if TYPE_CHECKING:  # pragma: no cover - torch is imported lazily at call time
    from torch_geometric.data import HeteroData

# Which node type sits at each end of each edge type (§6.1). The wind- and
# spatial-conditioned edges connect env stations to env stations; the auxiliary
# edges connect env stations to their auxiliary neighbours; the weather node
# broadcasts to every env station.
EDGE_ENDPOINTS: dict[EdgeType, tuple[NodeType, NodeType]] = {
    EdgeType.SPATIAL_PROXIMITY: (NodeType.ENV_STATION, NodeType.ENV_STATION),
    EdgeType.WIND_CONDITIONED: (NodeType.ENV_STATION, NodeType.ENV_STATION),
    EdgeType.ROAD_ADJACENCY: (NodeType.ENV_STATION, NodeType.TRAFFIC_COUNTER),
    EdgeType.TRANSIT_CORRIDOR: (NodeType.ENV_STATION, NodeType.BUS_STOP),
    EdgeType.WEATHER_INFLUENCE: (NodeType.WEATHER_NODE, NodeType.ENV_STATION),
}

# The PyG relation triple ``(src_type, rel, dst_type)`` each edge type becomes.
RELATION: dict[EdgeType, tuple[str, str, str]] = {
    et: (src.value, et.value, dst.value) for et, (src, dst) in EDGE_ENDPOINTS.items()
}


def node_index(snapshot: GraphSnapshot, node_type: NodeType) -> dict[str, int]:
    """Map each node id of ``node_type`` to its integer row index, in table order.

    The order is exactly the snapshot's node-table index order, which the build layer
    sorts deterministically, so the mapping is stable across runs.
    """
    table = snapshot.node_table(node_type)
    return {str(node_id): i for i, node_id in enumerate(table.index)}


def _edge_tensors(
    edges: pd.DataFrame,
    src_index: dict[str, int],
    dst_index: dict[str, int],
    torch_mod: Any,
) -> tuple[Any, Any]:
    """``(edge_index [2, E], edge_weight [E])`` for one edge table, dropping any edge
    whose endpoint is not a known node (defensive; the build layer never emits one).
    """
    if edges.empty or EDGE_SRC not in edges.columns:
        return (
            torch_mod.zeros((2, 0), dtype=torch_mod.long),
            torch_mod.zeros((0,), dtype=torch_mod.float32),
        )
    src_ids = edges[EDGE_SRC].astype(str).to_numpy()
    dst_ids = edges[EDGE_DST].astype(str).to_numpy()
    weights = edges[EDGE_WEIGHT].astype("float64").to_numpy()
    rows: list[int] = []
    cols: list[int] = []
    kept_w: list[float] = []
    for s, d, w in zip(src_ids, dst_ids, weights, strict=True):
        si = src_index.get(s)
        di = dst_index.get(d)
        if si is None or di is None:
            continue
        rows.append(si)
        cols.append(di)
        kept_w.append(float(w))
    edge_index = torch_mod.tensor([rows, cols], dtype=torch_mod.long)
    edge_weight = torch_mod.tensor(kept_w, dtype=torch_mod.float32)
    return edge_index, edge_weight


def _node_features(table: pd.DataFrame, torch_mod: Any) -> Any:
    """A finite ``[N, F]`` float tensor from a node table's numeric columns.

    When a table carries no numeric columns (the placeholder auxiliary types), returns
    a single constant feature per node — a positional placeholder, never an invented
    measurement. Rows are in table order.
    """
    n = len(table)
    numeric = table.select_dtypes(include=["number"])
    if numeric.empty:
        return torch_mod.ones((n, 1), dtype=torch_mod.float32)
    values = numeric.to_numpy(dtype="float64")
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    return torch_mod.tensor(values, dtype=torch_mod.float32)


def snapshot_to_hetero_data(snapshot: GraphSnapshot) -> HeteroData:
    """Build a PyG ``HeteroData`` from a snapshot: node features + typed edges.

    Pure in the snapshot: same snapshot in, byte-identical tensors out. Every edge
    type present in the snapshot becomes one relation, carrying its ``edge_index`` and
    an ``edge_weight`` attribute (the wind-conditioned weight for the dynamic edge, the
    static kernel weight for the others). Node features are the numeric columns of each
    node table, or a constant placeholder where a type carries none.
    """
    import torch
    from torch_geometric.data import HeteroData

    data = HeteroData()
    indices: dict[NodeType, dict[str, int]] = {}
    for node_type in NodeType:
        table = snapshot.node_table(node_type)
        indices[node_type] = {str(nid): i for i, nid in enumerate(table.index)}
        data[node_type.value].x = _node_features(table, torch)
        data[node_type.value].node_ids = [str(nid) for nid in table.index]

    for edge_type in EdgeType:
        src_type, dst_type = EDGE_ENDPOINTS[edge_type]
        edges = snapshot.edge_table(edge_type)
        edge_index, edge_weight = _edge_tensors(edges, indices[src_type], indices[dst_type], torch)
        rel = RELATION[edge_type]
        data[rel].edge_index = edge_index
        data[rel].edge_weight = edge_weight

    return data
