"""R12 ZERO_VARIANCE and R13 LOW_VARIANCE_DEGRADED."""

from __future__ import annotations

import numpy as np
from tests.support import series_rows

from provenance.detectors.variance import LowVarianceDetector, ZeroVarianceDetector


def test_r12_flags_frozen_series(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterLevel", [5.0] * 10, unit="m"))
    out = ZeroVarianceDetector().detect(frame, make_ctx(frame))
    assert set(out["reason_code"]) == {"R12"}
    assert len(out) == 10


def test_r12_negative_on_varying_series(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterLevel", [5.0, 5.1, 5.2, 5.0], unit="m"))
    assert ZeroVarianceDetector().detect(frame, make_ctx(frame)).empty


def test_r12_boundary_two_identical_values(make_frame, make_ctx) -> None:
    frame = make_frame(series_rows("S1", "WaterLevel", [5.0, 5.0], unit="m"))
    assert len(ZeroVarianceDetector().detect(frame, make_ctx(frame))) == 2


def _multi_station(flat_std: float, make_frame):
    rng = np.random.default_rng(0)
    rows: list[dict] = []
    for st in ("S1", "S2", "S3"):  # three peers with healthy variance
        rows += series_rows(st, "O3", list(60 + rng.normal(0, 20, 40)))
    rows += series_rows("S4", "O3", list(60 + rng.normal(0, flat_std, 40)))  # candidate
    return make_frame(rows)


def test_r13_flags_series_flat_relative_to_peers(make_frame, make_ctx) -> None:
    frame = _multi_station(0.1, make_frame)
    out = LowVarianceDetector().detect(frame, make_ctx(frame))
    assert set(out["reason_code"]) == {"R13"}
    assert set(out["station_id"]) == {"S4"}


def test_r13_negative_when_all_similar(make_frame, make_ctx) -> None:
    frame = _multi_station(20.0, make_frame)  # S4 as variable as its peers
    assert LowVarianceDetector().detect(frame, make_ctx(frame)).empty
