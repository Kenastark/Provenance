"""Test gate for the HST-GAT architecture (§6.4).

These are the phase-6 gate's architecture checks: if the model cannot overfit a tiny
batch, has the wrong shapes, is not permutation-equivariant, is not deterministic, or
produces a NaN on the real corpus shape, nothing downstream matters. The wind-bias
tests pin the two properties the brief calls out by name: zeroing the bias recovers a
plain HetGAT, and raising it monotonically shifts attention to the wind-connected
neighbour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from provenance.config.loading import load_graph_config, load_models_config
from provenance.graph import scenarios as S
from provenance.graph.snapshot import EdgeType
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.models.hstgat.data import Relation, TemporalGraphBatch, build_batch, truncate_batch
from provenance.models.hstgat.layers import GATMessage
from provenance.models.hstgat.model import (
    ENV_INPUT_DIM,
    HSTGAT,
    MODEL_RELATIONS,
    GCNBaseline,
    HSTGATConfig,
    masked_gaussian_nll,
)
from provenance.models.hstgat.train import MaskPlan, train_model
from provenance.schema import canonical as C


@pytest.fixture(scope="module")
def gcfg() -> dict:
    return load_graph_config()


@pytest.fixture(scope="module")
def mcfg() -> dict:
    return load_models_config()


@pytest.fixture(scope="module")
def config(mcfg: dict) -> HSTGATConfig:
    return HSTGATConfig.from_config(mcfg)


@pytest.fixture(scope="module")
def batch(gcfg: dict) -> TemporalGraphBatch:
    sc = S.corroborated_plume()
    return build_batch(sc.frame, sc.points, sc.wind, gcfg, target_parameter="PM10")


# --------------------------------------------------------------------- shapes
def test_forward_shapes_and_dtypes(batch: TemporalGraphBatch, config: HSTGATConfig) -> None:
    torch.manual_seed(0)
    model = HSTGAT(config)
    value_input = batch.target.clone()
    mask_flag = torch.zeros_like(batch.target)
    fc = model(value_input, mask_flag, batch)
    assert fc.mean.shape == (batch.n_times, batch.n_env)
    assert fc.variance.shape == (batch.n_times, batch.n_env)
    assert fc.mean.dtype == torch.float32
    assert (fc.variance > 0).all()  # variance is strictly positive (min_variance floor)


def test_gat_layer_shapes_for_every_edge_type(
    batch: TemporalGraphBatch, config: HSTGATConfig
) -> None:
    # A GAT message layer must produce the right shapes and dtypes for every one of the
    # five edge types, with attention of shape [E, heads].
    torch.manual_seed(0)
    heads = config.attention_heads
    out_dim = config.hidden_dim // heads
    seen = set()
    for edge_type in MODEL_RELATIONS:
        rel: Relation = batch.relations[edge_type]
        layer = GATMessage(config.hidden_dim, out_dim, heads)
        x_src = torch.randn(rel.n_src, config.hidden_dim)
        x_dst = torch.randn(batch.n_env, config.hidden_dim)
        out, alpha = layer(x_src, x_dst, rel.edge_index, return_attention=True)
        assert out.shape == (batch.n_env, heads * out_dim)
        assert out.dtype == torch.float32
        assert alpha is not None
        assert alpha.shape == (rel.edge_index.shape[1], heads)
        seen.add(edge_type)
    assert seen == set(MODEL_RELATIONS)  # every edge type exercised


def test_gcn_baseline_runs_and_is_smaller(batch: TemporalGraphBatch, config: HSTGATConfig) -> None:
    torch.manual_seed(0)
    gat = HSTGAT(config)
    torch.manual_seed(0)
    gcn = GCNBaseline(config)
    value_input = batch.target.clone()
    mask_flag = torch.zeros_like(batch.target)
    fc = gcn(value_input, mask_flag, batch)
    assert fc.mean.shape == (batch.n_times, batch.n_env)
    assert fc.attention == {}  # the baseline has no attention to export
    # The baseline is the ablation: no per-relation attention heads, so it is smaller.
    assert gcn.parameter_count() < gat.parameter_count()


# --------------------------------------------------------------------- no NaN, real shape
def _real_shape_corpus(n_stations: int = 18, n_hours: int = 720) -> tuple:
    rng = np.random.default_rng(7)
    start = pd.Timestamp("2026-05-01T00:00:00")
    times = [start + pd.Timedelta(hours=h) for h in range(n_hours)]
    points = [
        StationPoint(f"KER{i:02d}", 47.50 + 0.01 * i, 21.55 + 0.008 * i) for i in range(n_stations)
    ]
    rows = []
    for p in points:
        base = 20 + rng.normal(0, 3)
        for ts in times:
            rows.append(
                {
                    C.STATION_ID: p.station_id,
                    C.PARAMETER: "PM10",
                    C.TIMESTAMP: ts,
                    C.VALUE: float(max(0.0, base + rng.normal(0, 5))),
                    C.UNIT: "µg/m3",
                    C.SOURCE_FILE: "synthetic.csv",
                }
            )
            for param, val, unit in (
                ("Wind_Direction", 250.0, "degrees"),
                ("Wind_Speed", 4.0, "m/s"),
            ):
                rows.append(
                    {
                        C.STATION_ID: p.station_id,
                        C.PARAMETER: param,
                        C.TIMESTAMP: ts,
                        C.VALUE: val,
                        C.UNIT: unit,
                        C.SOURCE_FILE: "synthetic.csv",
                    }
                )
    frame = pd.DataFrame(rows)
    frame[C.INSTRUMENT_ID] = pd.Series([pd.NA] * len(frame), dtype="string")
    frame[C.TIMESTAMP] = pd.to_datetime(frame[C.TIMESTAMP])
    frame = C.validate(C.add_row_hash(frame))
    return frame, points, WindField.from_frame(frame)


@pytest.mark.demo_critical
def test_no_nan_or_inf_on_real_corpus_shape(gcfg: dict, config: HSTGATConfig) -> None:
    # 18 stations x 720 hours — the real network's shape (§5.1). A full forward pass
    # must stay finite everywhere.
    frame, points, wind = _real_shape_corpus()
    batch = build_batch(frame, points, wind, gcfg, target_parameter="PM10")
    assert batch.n_env == 18
    assert batch.n_times == 720
    torch.manual_seed(0)
    model = HSTGAT(config)
    value_input = batch.target.clone()
    mask_flag = torch.zeros_like(batch.target)
    with torch.no_grad():
        fc = model(value_input, mask_flag, batch)
    assert torch.isfinite(fc.mean).all()
    assert torch.isfinite(fc.variance).all()


# --------------------------------------------------------------------- determinism
def test_two_seeded_models_are_identical(batch: TemporalGraphBatch, config: HSTGATConfig) -> None:
    torch.manual_seed(config.seed)
    a = HSTGAT(config)
    torch.manual_seed(config.seed)
    b = HSTGAT(config)
    for pa, pb in zip(a.parameters(), b.parameters(), strict=True):
        assert torch.equal(pa, pb)
    value_input = batch.target.clone()
    mask_flag = torch.zeros_like(batch.target)
    with torch.no_grad():
        fa = a(value_input, mask_flag, batch)
        fb = b(value_input, mask_flag, batch)
    assert torch.equal(fa.mean, fb.mean)
    assert torch.equal(fa.variance, fb.variance)


# --------------------------------------------------------------------- permutation invariance
def _permute_env(batch: TemporalGraphBatch, perm: torch.Tensor) -> TemporalGraphBatch:
    """Relabel env node indices by ``perm`` (new position p holds old node perm[p])."""
    inv = torch.argsort(perm)  # old index -> new index

    def remap_env_rows(edge_index: torch.Tensor, remap_src: bool, remap_dst: bool) -> torch.Tensor:
        ei = edge_index.clone()
        if remap_src:
            ei[0] = inv[ei[0]]
        if remap_dst:
            ei[1] = inv[ei[1]]
        return ei

    relations = {}
    for et, rel in batch.relations.items():
        src_is_env = et in (EdgeType.SPATIAL_PROXIMITY, EdgeType.WIND_CONDITIONED)
        relations[et] = Relation(
            edge_type=rel.edge_type,
            src_type=rel.src_type,
            n_src=rel.n_src,
            edge_index=remap_env_rows(rel.edge_index, remap_src=src_is_env, remap_dst=True),
            static_weight=rel.static_weight,
            wind_weight=rel.wind_weight,
        )
    return TemporalGraphBatch(
        env_ids=[batch.env_ids[i] for i in perm.tolist()],
        times=batch.times,
        target=batch.target[:, perm],
        observed=batch.observed[:, perm],
        env_wind=batch.env_wind[:, perm],
        weather_wind=batch.weather_wind,
        relations=relations,
        mean=batch.mean,
        std=batch.std,
        target_parameter=batch.target_parameter,
    )


def test_permutation_invariance(batch: TemporalGraphBatch, config: HSTGATConfig) -> None:
    torch.manual_seed(0)
    model = HSTGAT(config)
    small = truncate_batch(batch, 8)
    value_input = small.target.clone()
    mask_flag = torch.zeros_like(small.target)
    with torch.no_grad():
        base = model(value_input, mask_flag, small)

    perm = torch.randperm(small.n_env, generator=torch.Generator().manual_seed(3))
    permuted = _permute_env(small, perm)
    with torch.no_grad():
        got = model(permuted.target.clone(), torch.zeros_like(permuted.target), permuted)

    # Prediction for the permuted node must equal the original node's prediction.
    assert torch.allclose(got.mean, base.mean[:, perm], atol=1e-5)
    assert torch.allclose(got.variance, base.variance[:, perm], atol=1e-5)


# --------------------------------------------------------------------- wind bias
def test_zeroing_wind_bias_recovers_plain_hetgat() -> None:
    torch.manual_seed(1)
    layer = GATMessage(4, 4, 1)
    x_src = torch.randn(3, 4)
    x_dst = torch.randn(2, 4)
    edge_index = torch.tensor([[0, 1, 2], [0, 1, 0]])
    bias = torch.tensor([0.9, 0.3, 0.5])
    out_zero, alpha_zero = layer(
        x_src, x_dst, edge_index, bias=bias, beta=0.0, return_attention=True
    )
    out_none, alpha_none = layer(
        x_src, x_dst, edge_index, bias=None, beta=0.0, return_attention=True
    )
    assert torch.equal(out_zero, out_none)
    assert alpha_zero is not None and alpha_none is not None
    assert torch.equal(alpha_zero, alpha_none)


def test_increasing_wind_bias_monotonically_increases_downwind_attention() -> None:
    torch.manual_seed(2)
    layer = GATMessage(4, 4, 1)
    # Two candidate sources into one destination, identical features so the logits are
    # equal; source 0 is the wind-connected (downwind-aligned) neighbour with the higher
    # bias, source 1 is off-axis.
    x_src = torch.stack([torch.ones(4), torch.ones(4)])
    x_dst = torch.ones(1, 4)
    edge_index = torch.tensor([[0, 1], [0, 0]])
    bias = torch.tensor([1.0, 0.0])
    last = -1.0
    for beta in (0.0, 0.5, 1.0, 2.0, 4.0):
        _, alpha = layer(x_src, x_dst, edge_index, bias=bias, beta=beta, return_attention=True)
        assert alpha is not None
        a0 = float(alpha[0, 0].detach())
        assert a0 >= last - 1e-9  # monotonically non-decreasing
        last = a0
    assert last > 0.9  # a strong bias overwhelmingly attends to the wind-connected neighbour


# --------------------------------------------------------------------- overfit a tiny batch
def test_overfit_eight_samples(gcfg: dict, mcfg: dict) -> None:
    sc = S.corroborated_plume()
    full = build_batch(sc.frame, sc.points, sc.wind, gcfg, target_parameter="PM10")
    tiny = truncate_batch(full, 6)  # keep the temporal loop short so this is sub-second
    hidden = torch.zeros_like(tiny.observed)
    for t, n in tiny.observed.nonzero()[:8]:
        hidden[t, n] = True
    assert int(hidden.sum()) == 8
    value_input = torch.where(hidden, torch.zeros_like(tiny.target), tiny.target)
    plan = MaskPlan(value_input=value_input, mask_flag=hidden.float(), eval_mask=hidden)
    trained = train_model(tiny, kind="hstgat", cfg=mcfg, epochs=250, fixed_plan=plan)
    with torch.no_grad():
        fc = trained.model(plan.value_input, plan.mask_flag, tiny)
        mse = float((fc.mean[hidden] - tiny.target[hidden]).pow(2).mean())
    assert mse < 1e-3  # drives reconstruction loss to near zero on 8 samples


def test_masked_gaussian_nll_is_zero_on_empty_mask() -> None:
    mean = torch.zeros(3, 2)
    var = torch.ones(3, 2)
    target = torch.ones(3, 2)
    empty = torch.zeros(3, 2, dtype=torch.bool)
    assert float(masked_gaussian_nll(mean, var, target, empty)) == 0.0


def test_env_input_dim_matches_encoder() -> None:
    # A guard so the feature layout and the encoder never silently drift apart.
    assert ENV_INPUT_DIM == 2 + 3
