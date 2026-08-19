"""Train the HST-GAT with a masked-autoencoder objective, honestly and reproducibly.

The training task is graph-conditioned imputation: hide a fraction of the known target
values, reconstruct them from their wind-weighted neighbours, and score the
reconstruction with a **masked Gaussian NLL** — the model predicts a mean *and* a
variance, so the loss rewards calibrated uncertainty, not just a good point estimate
(§7.7 needs the variance to conformalise later).

Every honesty rail the repo cares about is here:

* **Time-blocked splits, never random** (standing rule 7): the reconstruction is scored
  on a strictly-later time block than it trained on, via ``models.cv``.
* **Full seeding** (standing rule 8): seed, deterministic CPU ops, and a seeded mask
  generator, so two runs over the same corpus produce byte-identical weights.
* **A manifest per run**: seed, config hash, data checksum, git sha, metrics and the
  parameter count, written next to the artefact so a result can always be traced to
  the exact inputs that produced it.

No accuracy/F1 for propagation is computed anywhere (standing rule 4): the metrics are
reconstruction NLL/MSE of the imputation task, which describe the model, not a verdict.
"""

from __future__ import annotations

import json
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor, nn

from provenance.config.loading import load_models_config
from provenance.models.cv import assert_no_leakage, time_blocked_splits
from provenance.models.hstgat.data import TemporalGraphBatch
from provenance.models.hstgat.model import (
    HSTGAT,
    GCNBaseline,
    HSTGATConfig,
    masked_gaussian_nll,
)

# The persisted artefact name per kind (the class key stays "hstgat"; the artefact and
# its model card are the friendlier "hst-gat").
NAME_FOR_KIND: dict[str, str] = {"hstgat": "hst-gat", "gcn": "gcn"}
_KINDS = tuple(NAME_FOR_KIND)


def _build_model(kind: str, config: HSTGATConfig) -> HSTGAT | GCNBaseline:
    """Construct the requested model, typed concretely so ``parameter_count`` resolves."""
    if kind == "hstgat":
        return HSTGAT(config)
    if kind == "gcn":
        return GCNBaseline(config)
    raise ValueError(f"Unknown model kind {kind!r}; expected one of {sorted(NAME_FOR_KIND)}.")


def set_seed(seed: int) -> None:
    """Seed every RNG the training loop touches (standing rule 8).

    Also pins torch to a single intra-op thread: CPU determinism is only guaranteed
    single-threaded (ADR 0009), and on macOS the multiple bundled OpenMP runtimes
    (torch/numba/sklearn/scipy) can race a background thread and crash a large
    ``torch.tensor`` build. One thread removes both problems; the models here are tiny,
    so there is nothing to parallelise anyway.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def resolve_device(name: str) -> torch.device:
    """Resolve a device name, falling back to CPU (with a warning) if unavailable.

    Determinism is only guaranteed on CPU (ADR 0009); ``mps`` is opt-in and degrades
    to CPU rather than crashing, so a config copied from a Mac still runs in CI.
    """
    if name == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if name == "cuda" and torch.cuda.is_available():  # pragma: no cover - no GPU in CI
        return torch.device("cuda")
    if name not in ("cpu", "mps", "cuda"):  # pragma: no cover - defensive
        import warnings

        warnings.warn(f"Unknown torch device {name!r}; using cpu.", stacklevel=2)
    elif name != "cpu":
        import warnings

        warnings.warn(f"Device {name!r} unavailable; using cpu (determinism holds).", stacklevel=2)
    return torch.device("cpu")


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover - git absent in some sandboxes
        return "unknown"


@dataclass(frozen=True, slots=True)
class MaskPlan:
    """A masked-AE plan: which known cells are hidden, and the tensors the model sees."""

    value_input: Tensor
    mask_flag: Tensor
    eval_mask: Tensor  # hidden AND originally observed — where the loss is computed


def make_mask(batch: TemporalGraphBatch, fraction: float, generator: torch.Generator) -> MaskPlan:
    """Hide ``fraction`` of the observed cells, seeded, for the reconstruction task."""
    observed = batch.observed
    probs = torch.rand(observed.shape, generator=generator)
    hidden = observed & (probs < fraction)
    value_input = torch.where(hidden, torch.zeros_like(batch.target), batch.target)
    mask_flag = hidden.to(batch.target.dtype)
    return MaskPlan(value_input=value_input, mask_flag=mask_flag, eval_mask=hidden)


@dataclass(frozen=True, slots=True)
class TrainedModel:
    """A trained neural model plus its full provenance record (the card is built from this)."""

    kind: str
    model: nn.Module
    config: HSTGATConfig
    mean: float
    std: float
    target_parameter: str
    env_ids: list[str]
    data_checksum: str
    git_sha: str
    seed: int
    parameter_count: int
    metrics: dict[str, Any]
    window_start: str
    window_end: str

    @property
    def name(self) -> str:
        return NAME_FOR_KIND.get(self.kind, self.kind)

    @property
    def version(self) -> str:
        return f"v1-{self.data_checksum[:8]}"

    @property
    def stem(self) -> str:
        return f"{self.name}-{self.version}"

    def manifest(self, config_hash: str) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "version": self.version,
            "seed": self.seed,
            "config_hash": config_hash,
            "data_checksum": self.data_checksum,
            "git_sha": self.git_sha,
            "parameter_count": self.parameter_count,
            "target_parameter": self.target_parameter,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "metrics": self.metrics,
        }


def _evaluate(
    model: nn.Module, batch: TemporalGraphBatch, test_idx: np.ndarray
) -> dict[str, float]:
    """Held-out reconstruction NLL/MSE on a strictly-later time block.

    The whole observed test-block is hidden and reconstructed from neighbours + history
    — a graph-conditioned imputation score, not a verdict accuracy.
    """
    model.eval()
    with torch.no_grad():
        test_rows = torch.zeros(batch.n_times, dtype=torch.bool)
        test_rows[torch.tensor(test_idx, dtype=torch.long)] = True
        hidden = batch.observed & test_rows.unsqueeze(-1)
        value_input = torch.where(hidden, torch.zeros_like(batch.target), batch.target)
        mask_flag = hidden.to(batch.target.dtype)
        fc = model(value_input, mask_flag, batch)
        nll = float(masked_gaussian_nll(fc.mean, fc.variance, batch.target, hidden))
        if hidden.sum() > 0:
            diff = (fc.mean[hidden] - batch.target[hidden]) * batch.std
            mse = float((diff.pow(2)).mean())
            n = int(hidden.sum())
        else:  # pragma: no cover - defensive
            mse, n = float("nan"), 0
    return {
        "heldout_nll": round(nll, 6),
        "heldout_rmse_physical": round(mse**0.5, 6),
        "n_heldout": n,
    }


def train_model(
    batch: TemporalGraphBatch,
    *,
    kind: str = "hstgat",
    cfg: dict[str, Any] | None = None,
    epochs: int | None = None,
    resample_mask: bool = True,
    fixed_plan: MaskPlan | None = None,
    data_checksum: str = "unknown",
) -> TrainedModel:
    """Train an HST-GAT (or the GCN baseline) on a corpus batch, reproducibly.

    Args:
        batch: the tensorised graph over the target parameter.
        kind: ``"hstgat"`` or ``"gcn"`` (the baseline).
        cfg: models config (defaults to ``models.yaml``).
        epochs: overrides the configured epoch count (the overfit test uses a few).
        resample_mask: re-draw the hidden set each epoch (generalisation). The
            overfit-a-tiny-batch gate passes ``False`` for a fixed target set.
        fixed_plan: an explicit masked-AE plan reused every epoch — the
            overfit-a-tiny-batch gate passes one hiding exactly its handful of cells.
        data_checksum: the corpus checksum, threaded into the version and the card.
    """
    cfg = cfg or load_models_config()
    config = HSTGATConfig.from_config(cfg)
    if kind not in _KINDS:
        raise ValueError(f"Unknown model kind {kind!r}; expected one of {sorted(_KINDS)}.")
    set_seed(config.seed)
    device = resolve_device(config.device)

    model = _build_model(kind, config)
    model.to(device)  # in-place device move; return value intentionally ignored
    n_epochs = config.epochs if epochs is None else epochs

    # Time-blocked split: train on the early blocks, score reconstruction on the last.
    times_index = pd.DatetimeIndex(batch.times)
    splits = time_blocked_splits(times_index, n_splits=max(1, config.n_splits))
    assert_no_leakage(times_index, splits)
    train_idx, test_idx = splits[-1]
    train_rows = torch.zeros(batch.n_times, dtype=torch.bool)
    train_rows[torch.tensor(train_idx, dtype=torch.long)] = True

    optimiser = torch.optim.Adam(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    generator = torch.Generator().manual_seed(config.seed)
    # For a fixed-target overfit, draw one mask up front and reuse it every epoch (or
    # accept an explicit plan the caller pinned to an exact set of cells).
    fixed = (
        fixed_plan
        if fixed_plan is not None
        else (None if resample_mask else make_mask(batch, config.mask_fraction, generator))
    )

    model.train()
    last_loss = float("nan")
    for _ in range(n_epochs):
        plan = fixed if fixed is not None else make_mask(batch, config.mask_fraction, generator)
        # Only score cells inside the training time-block (never leak the test block).
        eval_mask = plan.eval_mask & train_rows.unsqueeze(-1) if fixed is None else plan.eval_mask
        optimiser.zero_grad()
        fc = model(plan.value_input, plan.mask_flag, batch)
        loss = masked_gaussian_nll(fc.mean, fc.variance, batch.target, eval_mask)
        loss.backward()  # type: ignore[no-untyped-call]
        optimiser.step()
        last_loss = float(loss.detach())

    metrics = {"final_train_nll": round(last_loss, 6)}
    if resample_mask:
        metrics.update(_evaluate(model, batch, test_idx))

    model.eval()
    return TrainedModel(
        kind=kind,
        model=model,
        config=config,
        mean=batch.mean,
        std=batch.std,
        target_parameter=batch.target_parameter,
        env_ids=list(batch.env_ids),
        data_checksum=data_checksum,
        git_sha=_git_sha(),
        seed=config.seed,
        parameter_count=model.parameter_count(),
        metrics=metrics,
        window_start=batch.times[0].isoformat(),
        window_end=batch.times[-1].isoformat(),
    )


def write_manifest(trained: TrainedModel, config_hash: str, out_dir: Path) -> Path:
    """Write the run manifest next to the artefact (deterministic, sorted keys)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{trained.stem}.manifest.json"
    payload = json.dumps(
        trained.manifest(config_hash), indent=2, sort_keys=True, ensure_ascii=False
    )
    path.write_text(payload + "\n", encoding="utf-8")
    return path
