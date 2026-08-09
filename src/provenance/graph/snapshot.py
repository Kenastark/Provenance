"""The :class:`GraphSnapshot` — the whole heterogeneous graph at one instant.

This is the boundary the phase brief asks to be drawn on purpose. Today a snapshot
is node tables and edge tables as plain pandas frames over numpy — no torch, no
PyG, importable and testable anywhere. Phase 6 will back the *same accessors*
(:meth:`node_table`, :meth:`edge_table`) with a PyG ``HeteroData`` object and add a
``to_hetero_data()`` that materialises tensors, **without changing a single
caller**. Callers speak node-type and edge-type keys and get frames back; how those
frames are stored is the snapshot's private business.

Determinism (standing rule 8): node tables are indexed by a stable node id and edge
tables are sorted by ``(src, dst)``, so two builds over the same inputs are
byte-identical and free of NaN/inf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pandas as pd


class NodeType(StrEnum):
    """The four node types the network graph carries (§6.1)."""

    ENV_STATION = "EnvStation"
    TRAFFIC_COUNTER = "TrafficCounter"
    BUS_STOP = "BusStop"
    WEATHER_NODE = "WeatherNode"


class EdgeType(StrEnum):
    """The five edge types (§6.1). Only ``wind_conditioned`` is time-varying."""

    SPATIAL_PROXIMITY = "spatial_proximity"
    WIND_CONDITIONED = "wind_conditioned"
    ROAD_ADJACENCY = "road_adjacency"
    TRANSIT_CORRIDOR = "transit_corridor"
    WEATHER_INFLUENCE = "weather_influence"


# Column contracts the rest of the layer relies on.
NODE_ID = "node_id"
EDGE_SRC = "src"
EDGE_DST = "dst"
EDGE_WEIGHT = "weight"


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    """Node and edge tables per type at a single timestamp.

    ``nodes[NodeType]`` is a frame indexed by :data:`NODE_ID`; ``edges[EdgeType]`` is
    a frame with at least ``src``, ``dst``, ``weight``. ``wind_provenance`` on a
    wind-edge row records whether its wind came from a station-local sensor or the
    city-level fallback (KER15 carries no wind sensor, so this is never assumed).
    """

    timestamp: pd.Timestamp
    nodes: dict[NodeType, pd.DataFrame]
    edges: dict[EdgeType, pd.DataFrame]
    meta: dict[str, Any] = field(default_factory=dict)

    def node_table(self, node_type: NodeType) -> pd.DataFrame:
        """The node frame for ``node_type`` (empty frame if the type is absent)."""
        return self.nodes.get(node_type, pd.DataFrame())

    def edge_table(self, edge_type: EdgeType) -> pd.DataFrame:
        """The edge frame for ``edge_type`` (empty frame if the type is absent)."""
        return self.edges.get(edge_type, pd.DataFrame())

    def node_count(self, node_type: NodeType) -> int:
        return len(self.node_table(node_type))

    def edge_count(self, edge_type: EdgeType) -> int:
        return len(self.edge_table(edge_type))

    def has_nan(self) -> bool:
        """True if any node or edge table carries a NaN/inf in a numeric column.

        The snapshot must be finite everywhere (a zero-wind edge is 0.0, never NaN),
        so this is what the corpus-wide invariant test asserts is always False.
        """
        import numpy as np

        for frame in (*self.nodes.values(), *self.edges.values()):
            numeric = frame.select_dtypes(include=["number"])
            if numeric.empty:
                continue
            values = numeric.to_numpy(dtype="float64")
            if not np.isfinite(values).all():
                return True
        return False

    def to_hetero_data(self) -> Any:  # pragma: no cover - phase 6
        """Materialise a PyG ``HeteroData`` view. Implemented in phase 6.

        Deliberately unimplemented now: the neural stack (PyTorch Geometric) is a
        phase-6 dependency, and the whole point of this boundary is that it can be
        added here without any caller of :meth:`node_table` / :meth:`edge_table`
        changing. Raising keeps the seam explicit rather than pretending it exists.
        """
        raise NotImplementedError(
            "GraphSnapshot.to_hetero_data() lands in phase 6 (HST-GAT). The numpy/pandas "
            "node and edge tables are the stable interface; PyG backs them later."
        )

    def summary(self) -> dict[str, Any]:
        """A small, JSON-safe description of the snapshot's shape."""
        return {
            "timestamp": pd.Timestamp(self.timestamp).isoformat(),
            "nodes": {nt.value: self.node_count(nt) for nt in NodeType},
            "edges": {et.value: self.edge_count(et) for et in EdgeType},
        }
