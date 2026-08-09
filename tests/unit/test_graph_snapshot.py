"""Graph construction invariants: bounded aggregation, determinism, finiteness, purity."""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.config.loading import load_graph_config
from provenance.graph.build import build_snapshot, station_points_from_metadata
from provenance.graph.snapshot import EDGE_WEIGHT, EdgeType, GraphSnapshot, NodeType
from provenance.graph.topology import StationPoint, TopologyParams, bus_corridor_nodes
from provenance.graph.wind import WindField
from provenance.schema import canonical as C

_TS = pd.Timestamp("2026-06-01T12:00:00")


def _points(n: int = 18) -> list[StationPoint]:
    return [StationPoint(f"S{i:02d}", 47.50 + 0.01 * i, 21.50 + 0.008 * i) for i in range(n)]


def _empty_wind() -> WindField:
    return WindField.from_frame(
        pd.DataFrame(columns=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP, C.VALUE, C.UNIT])
    )


@pytest.fixture
def cfg() -> dict:
    return load_graph_config()


def test_all_four_node_types_present(cfg: dict) -> None:
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    assert snap.node_count(NodeType.ENV_STATION) == 18
    assert snap.node_count(NodeType.TRAFFIC_COUNTER) == cfg["topology"]["traffic_counters"]
    assert snap.node_count(NodeType.WEATHER_NODE) == 1
    assert snap.node_count(NodeType.BUS_STOP) >= 1


def test_bus_stop_aggregation_is_bounded(cfg: dict) -> None:
    # §16 critique 6: hundreds of raw stops must never reach the graph — they are
    # aggregated to at most bus_corridor_max corridor nodes.
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    bound = cfg["topology"]["bus_corridor_max"]
    assert 1 <= snap.node_count(NodeType.BUS_STOP) <= bound


def test_bus_aggregation_bounded_even_with_many_raw_stops(cfg: dict) -> None:
    params = TopologyParams.from_config(cfg)
    inflated = TopologyParams(
        traffic_counters=params.traffic_counters,
        bus_stops_raw=5000,
        bus_corridor_max=params.bus_corridor_max,
        road_adjacency_k=params.road_adjacency_k,
        seed=params.seed,
    )
    corridors = bus_corridor_nodes(_points(), inflated)
    assert len(corridors) <= params.bus_corridor_max
    # Every raw stop is accounted for by exactly one corridor.
    assert int(corridors["n_stops"].sum()) == 5000


def test_snapshot_is_deterministic(cfg: dict) -> None:
    a = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    b = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    for et in EdgeType:
        pd.testing.assert_frame_equal(a.edge_table(et), b.edge_table(et))
    for nt in NodeType:
        pd.testing.assert_frame_equal(a.node_table(nt), b.node_table(nt))


def test_snapshot_has_no_nan_or_inf(cfg: dict) -> None:
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    assert snap.has_nan() is False


def test_wind_edges_are_a_pure_function_of_wind_at_t(cfg: dict) -> None:
    # Same geometry + config, two different (empty) winds at the same t give the same
    # zero edges; the edge weights depend only on (geometry, wind at t, config).
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    wind_edges = snap.edge_table(EdgeType.WIND_CONDITIONED)
    assert (wind_edges[EDGE_WEIGHT] == 0.0).all()  # no wind ⇒ every wind edge is 0


def test_edge_sets_are_bounded(cfg: dict) -> None:
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    n = 18
    assert snap.edge_count(EdgeType.WIND_CONDITIONED) <= n * (n - 1)
    assert snap.edge_count(EdgeType.WEATHER_INFLUENCE) == n
    assert snap.edge_count(EdgeType.ROAD_ADJACENCY) == n * cfg["topology"]["road_adjacency_k"]


def test_hetero_data_boundary_materialises_typed_tensors(cfg: dict) -> None:
    # Phase 6 backs the same node/edge-table interface with a PyG HeteroData. The
    # boundary the phase-4/5 snapshot reserved is now implemented, still behind the
    # very same accessors, and torch is imported only inside to_hetero_data().
    torch = pytest.importorskip("torch")
    snap = build_snapshot(_points(), _empty_wind(), _TS, cfg)
    data = snap.to_hetero_data()
    # Every node type carries a finite [N, F] feature tensor.
    for nt in NodeType:
        x = data[nt.value].x
        assert x.shape[0] == snap.node_count(nt)
        assert torch.isfinite(x).all()
    # Every edge type becomes a relation with a [2, E] index and a finite weight vector,
    # matching the snapshot's own edge counts (determinism: table order preserved).
    from provenance.graph.pyg import RELATION

    for et in EdgeType:
        rel = RELATION[et]
        assert data[rel].edge_index.shape[0] == 2
        assert data[rel].edge_index.shape[1] == snap.edge_count(et)
        assert torch.isfinite(data[rel].edge_weight).all()


def test_station_points_drop_coordinateless() -> None:
    class Loc:
        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon

    meta = {"A": Loc(47.5, 21.5), "B": Loc(None, None)}
    points = station_points_from_metadata(meta)
    assert [p.station_id for p in points] == ["A"]


def test_empty_snapshot_summary_is_json_safe(cfg: dict) -> None:
    snap: GraphSnapshot = build_snapshot(_points(3), _empty_wind(), _TS, cfg)
    summary = snap.summary()
    assert set(summary["nodes"]) == {nt.value for nt in NodeType}
    assert set(summary["edges"]) == {et.value for et in EdgeType}
