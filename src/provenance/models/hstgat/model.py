"""The HST-GAT: heterogeneous spatio-temporal graph attention (§6.4), and its GCN foil.

    h_i(t) = GRU( h_i(t-1), HetGAT_aggregate({h_j(t) : j ∈ N(i)}, edge_weights(t)) )

Read literally: at each hour every EnvStation aggregates a message from its neighbours
across *all* edge types with type-specific attention, and that message drives a GRU
cell carrying the station's own memory forward one step. The wind-conditioned weight
enters the wind relation's attention as an additive pre-softmax bias (see
:mod:`.layers`), so the physical prior guides — but never hard-masks — where the model
looks; the data can override it.

The head predicts a **mean and a variance** per (hour, station), not a point estimate,
because a graph-conditioned expectation with no notion of its own uncertainty cannot be
conformalised honestly (§7.7). The model is deliberately tiny: the binding constraint
is 720 timesteps per station (§5.1), so capacity is spent on structure, not width. The
parameter count is logged in the model card and justified there.

:class:`GCNBaseline` is the ablation the blueprint asks for: the same temporal head over
a plain degree-normalised graph convolution on the spatial edges only — no attention,
no wind, no heterogeneity — so the model card can show what each of those buys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor, nn

from provenance.graph.snapshot import EdgeType
from provenance.models.hstgat.data import WIND_FEATURE_DIM, Relation, TemporalGraphBatch
from provenance.models.hstgat.layers import GATMessage, GCNMessage

# Env self-input: [masked value, mask flag] ++ wind features.
ENV_INPUT_DIM = 2 + WIND_FEATURE_DIM

# The relations the model aggregates into every EnvStation, in a fixed order so two
# builds wire identical parameters (determinism, standing rule 8).
MODEL_RELATIONS: tuple[EdgeType, ...] = (
    EdgeType.SPATIAL_PROXIMITY,
    EdgeType.WIND_CONDITIONED,
    EdgeType.WEATHER_INFLUENCE,
    EdgeType.ROAD_ADJACENCY,
    EdgeType.TRANSIT_CORRIDOR,
)


@dataclass(frozen=True, slots=True)
class HSTGATConfig:
    """Architecture + training knobs, read from ``models.yaml`` (``hstgat`` block)."""

    target_parameter: str
    hidden_dim: int
    attention_heads: int
    wind_bias_beta_init: float
    mask_fraction: float
    epochs: int
    learning_rate: float
    weight_decay: float
    min_variance: float
    n_splits: int
    seed: int
    device: str

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> HSTGATConfig:
        h = cfg["hstgat"]
        hidden = int(h["hidden_dim"])
        heads = int(h["attention_heads"])
        if hidden % heads != 0:
            raise ValueError(
                f"hidden_dim ({hidden}) must be divisible by attention_heads ({heads})."
            )
        return cls(
            target_parameter=str(h["target_parameter"]),
            hidden_dim=hidden,
            attention_heads=heads,
            wind_bias_beta_init=float(h["wind_bias_beta_init"]),
            mask_fraction=float(h["mask_fraction"]),
            epochs=int(h["epochs"]),
            learning_rate=float(h["learning_rate"]),
            weight_decay=float(h["weight_decay"]),
            min_variance=float(h["min_variance"]),
            n_splits=int(h["n_splits"]),
            seed=int(h["seed"]),
            device=str(h.get("device", "cpu")),
        )


@dataclass(frozen=True, slots=True)
class Forecast:
    """A model forward pass: standardised mean/variance per (hour, station) + attention.

    ``attention`` maps each relation to ``(edge_index [2, E], alpha [E])`` at the
    requested export step (mean over heads), for the map overlay (§8).
    """

    mean: Tensor
    variance: Tensor
    attention: dict[EdgeType, tuple[Tensor, Tensor]]


class _TemporalHead(nn.Module):
    """Shared per-station GRU memory + Gaussian (mean, variance) decoder."""

    def __init__(self, hidden_dim: int, min_variance: float):
        super().__init__()
        self.gru = nn.GRUCell(hidden_dim, hidden_dim)
        self.decoder = nn.Linear(hidden_dim, 2)
        self.min_variance = min_variance
        self.softplus = nn.Softplus()

    def step(self, message: Tensor, hidden: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        hidden = self.gru(message, hidden)
        out = self.decoder(hidden)
        mean = out[:, 0]
        variance = self.softplus(out[:, 1]) + self.min_variance
        return hidden, mean, variance


class HSTGAT(nn.Module):
    """The heterogeneous spatio-temporal graph-attention model (§6.4)."""

    def __init__(self, config: HSTGATConfig):
        super().__init__()
        self.config = config
        h = config.hidden_dim
        heads = config.attention_heads
        out_dim = h // heads

        self.env_enc = nn.Linear(ENV_INPUT_DIM, h)
        self.weather_enc = nn.Linear(WIND_FEATURE_DIM, h)
        # Learned placeholder representations for the auxiliary source types, which carry
        # no confirmed time-varying features yet (ADR 0003) — never invented signal.
        self.traffic_emb = nn.Parameter(torch.zeros(h))
        self.corridor_emb = nn.Parameter(torch.zeros(h))

        self.messengers = nn.ModuleDict(
            {et.value: GATMessage(h, out_dim, heads) for et in MODEL_RELATIONS}
        )
        self.wind_beta = nn.Parameter(torch.tensor(float(config.wind_bias_beta_init)))
        self.head = _TemporalHead(h, config.min_variance)

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def _src_features(
        self, edge_type: EdgeType, env_x: Tensor, weather_x: Tensor, rel: Relation
    ) -> Tensor:
        if edge_type in (EdgeType.SPATIAL_PROXIMITY, EdgeType.WIND_CONDITIONED):
            return env_x
        if edge_type is EdgeType.WEATHER_INFLUENCE:
            return weather_x
        if edge_type is EdgeType.ROAD_ADJACENCY:
            return self.traffic_emb.unsqueeze(0).expand(rel.n_src, -1)
        return self.corridor_emb.unsqueeze(0).expand(rel.n_src, -1)

    def forward(
        self,
        value_input: Tensor,
        mask_flag: Tensor,
        batch: TemporalGraphBatch,
        *,
        return_attention_step: int | None = None,
    ) -> Forecast:
        """Run the model over the whole sequence.

        Args:
            value_input: ``[T, n_env]`` standardised target with hidden cells set to 0.
            mask_flag: ``[T, n_env]`` 1 where the cell was hidden (masked-AE), else 0.
            batch: the tensorised graph (relations, wind features, wind weights).
            return_attention_step: hour whose per-relation attention to export
                (defaults to the last hour).

        Returns:
            A :class:`Forecast` with standardised mean/variance ``[T, n_env]``.
        """
        n_t, n_env = value_input.shape
        att_step = n_t - 1 if return_attention_step is None else return_attention_step
        hidden = value_input.new_zeros((n_env, self.config.hidden_dim))
        means: list[Tensor] = []
        variances: list[Tensor] = []
        attention: dict[EdgeType, tuple[Tensor, Tensor]] = {}

        for t in range(n_t):
            env_in = torch.cat(
                [value_input[t].unsqueeze(-1), mask_flag[t].unsqueeze(-1), batch.env_wind[t]],
                dim=-1,
            )
            env_x = self.env_enc(env_in)
            weather_x = self.weather_enc(batch.weather_wind[t]).unsqueeze(0)

            message = env_x.new_zeros((n_env, self.config.hidden_dim))
            for edge_type in MODEL_RELATIONS:
                rel = batch.relations[edge_type]
                messenger = self.messengers[edge_type.value]
                x_src = self._src_features(edge_type, env_x, weather_x, rel)
                bias = None
                beta: Tensor | float = 0.0
                if edge_type is EdgeType.WIND_CONDITIONED and rel.wind_weight is not None:
                    bias = rel.wind_weight[t]
                    beta = self.wind_beta
                want_att = t == att_step
                out, alpha = messenger(
                    x_src, env_x, rel.edge_index, bias=bias, beta=beta, return_attention=want_att
                )
                message = message + out
                if want_att and alpha is not None:
                    attention[edge_type] = (rel.edge_index, alpha.mean(dim=-1))

            hidden, mean, variance = self.head.step(message, hidden)
            means.append(mean)
            variances.append(variance)

        return Forecast(
            mean=torch.stack(means), variance=torch.stack(variances), attention=attention
        )


class GCNBaseline(nn.Module):
    """The baseline: a plain GCN over the spatial edges + the same temporal head.

    No attention, no wind bias, no heterogeneity — the ablation the blueprint specifies
    so the card can show what the attention and the wind prior actually buy.
    """

    def __init__(self, config: HSTGATConfig):
        super().__init__()
        self.config = config
        h = config.hidden_dim
        self.env_enc = nn.Linear(ENV_INPUT_DIM, h)
        self.conv = GCNMessage(h, h)
        self.head = _TemporalHead(h, config.min_variance)

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(
        self,
        value_input: Tensor,
        mask_flag: Tensor,
        batch: TemporalGraphBatch,
        *,
        return_attention_step: int | None = None,
    ) -> Forecast:
        n_t, n_env = value_input.shape
        hidden = value_input.new_zeros((n_env, self.config.hidden_dim))
        spatial = batch.relations[EdgeType.SPATIAL_PROXIMITY].edge_index
        means: list[Tensor] = []
        variances: list[Tensor] = []
        for t in range(n_t):
            env_in = torch.cat(
                [value_input[t].unsqueeze(-1), mask_flag[t].unsqueeze(-1), batch.env_wind[t]],
                dim=-1,
            )
            env_x = self.env_enc(env_in)
            message = self.conv(env_x, env_x, spatial)
            hidden, mean, variance = self.head.step(message, hidden)
            means.append(mean)
            variances.append(variance)
        return Forecast(mean=torch.stack(means), variance=torch.stack(variances), attention={})


def masked_gaussian_nll(mean: Tensor, variance: Tensor, target: Tensor, mask: Tensor) -> Tensor:
    """Mean Gaussian negative log-likelihood over the entries where ``mask`` is True.

    ``0.5 * (log(2π·var) + (y-μ)²/var)`` averaged over masked cells. Returns 0 when the
    mask is empty (a degenerate batch), so the training loop never divides by zero.
    """
    if mask.sum() == 0:
        return mean.new_zeros(())
    sel = mask
    var = variance[sel]
    diff = target[sel] - mean[sel]
    two_pi = mean.new_tensor(2.0 * torch.pi)
    nll = 0.5 * (torch.log(two_pi * var) + diff.pow(2) / var)
    return nll.mean()
