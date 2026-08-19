"""Rebuilding the graph for one timestep must stay under the 100 ms budget."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from provenance.config.loading import load_graph_config
from provenance.graph.build import build_snapshot
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.schema import canonical as C

_BUDGET_MS = 100.0


def _points(n: int = 18) -> list[StationPoint]:
    return [StationPoint(f"S{i:02d}", 47.50 + 0.01 * i, 21.50 + 0.008 * i) for i in range(n)]


@pytest.mark.demo_critical
def test_single_timestep_build_under_budget() -> None:
    cfg = load_graph_config()
    points = _points()
    wind = WindField.from_frame(
        pd.DataFrame(columns=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP, C.VALUE, C.UNIT])
    )
    at = pd.Timestamp("2026-06-01T12:00:00")

    build_snapshot(points, wind, at, cfg)  # warm import/allocation paths
    timings_ms: list[float] = []
    for _ in range(5):
        start = time.perf_counter()
        build_snapshot(points, wind, at, cfg)
        timings_ms.append((time.perf_counter() - start) * 1000.0)

    best_ms = min(timings_ms)
    assert best_ms < _BUDGET_MS, f"graph rebuild took {best_ms:.1f} ms (budget {_BUDGET_MS} ms)"
