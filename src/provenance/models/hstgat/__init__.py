"""HST-GAT: the heterogeneous spatio-temporal graph-attention model (phase 6, §6.4).

The research contribution. A small heterogeneous graph-attention network with a
per-station GRU memory learns a graph-conditioned expectation of each station's reading
from its wind-weighted neighbours (masked-autoencoder objective, Gaussian NLL), which
the propagation adjudicator can use in place of the analytic plume prior — behind a
feature flag, with an automatic analytic fallback. Its attention is inspectable (§8) and
its outputs are wrapped with split-conformal intervals (§7.7).

The layering is deliberate: this package may import ``graph`` and torch, but ``graph``
never imports it — the learned expectation reaches the adjudicator only through the
``graph.ExpectationProvider`` Protocol (dependency injection), so the import graph stays
acyclic and the statistics layers never need torch.
"""

from provenance.models.hstgat.data import TemporalGraphBatch, build_batch, truncate_batch
from provenance.models.hstgat.model import (
    HSTGAT,
    GCNBaseline,
    HSTGATConfig,
    masked_gaussian_nll,
)
from provenance.models.hstgat.train import TrainedModel, train_model

__all__ = [
    "HSTGAT",
    "GCNBaseline",
    "HSTGATConfig",
    "TemporalGraphBatch",
    "TrainedModel",
    "build_batch",
    "masked_gaussian_nll",
    "train_model",
    "truncate_batch",
]
