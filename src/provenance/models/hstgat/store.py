"""Persist and reload the HST-GAT, with the same card discipline as the tree models.

Two rules, identical to :mod:`provenance.models.registry` (§5, standing rule 6):

* **A model without a valid card must not load.** The artefact carries the training
  data checksum; the card sidecar carries it too; a mismatch (or a missing card)
  raises rather than loading a model whose provenance cannot be verified.
* **Graceful degradation.** ``load_latest`` returns ``None`` when no artefact exists,
  so the adjudicator falls back to the analytic prior and says so — a missing learned
  model is a normal state, not an error.

Kept in the ``hstgat`` package (not the shared registry) so importing the serving-time
registry never drags torch onto a machine that only runs the statistics layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn

from provenance.config.settings import get_settings
from provenance.models.hstgat.card import build_card
from provenance.models.hstgat.model import HSTGAT, GCNBaseline, HSTGATConfig
from provenance.models.hstgat.train import TrainedModel
from provenance.models.registry import ModelCardMissingError

_MODEL_SUFFIX = ".pt"
_CARD_SUFFIX = ".card.json"
_KINDS: dict[str, type[nn.Module]] = {"hstgat": HSTGAT, "gcn": GCNBaseline}


@dataclass(frozen=True, slots=True)
class LoadedModel:
    """A reloaded model plus the metadata a forecast needs to interpret its outputs."""

    kind: str
    model: nn.Module
    config: HSTGATConfig
    mean: float
    std: float
    target_parameter: str
    env_ids: list[str]
    data_checksum: str
    conformal: dict[str, Any] | None = None
    """The persisted split-conformal calibrator (alpha, q, normalised, n_calibration), or
    ``None`` if the model was saved without one. Used to attach a calibrated interval to
    the learned expectation at inference — the interval is meaningless without the ``q``
    computed on the held-out calibration block, so it travels with the artefact."""


def _artefacts_dir(artefacts_dir: Path | None) -> Path:
    return Path(artefacts_dir) if artefacts_dir is not None else get_settings().artefacts_dir


def _state_payload(trained: TrainedModel, conformal: dict[str, Any] | None) -> dict[str, Any]:
    c = trained.config
    return {
        "kind": trained.kind,
        "state_dict": trained.model.state_dict(),
        "conformal": conformal,
        "config": {
            "target_parameter": c.target_parameter,
            "hidden_dim": c.hidden_dim,
            "attention_heads": c.attention_heads,
            "wind_bias_beta_init": c.wind_bias_beta_init,
            "mask_fraction": c.mask_fraction,
            "epochs": c.epochs,
            "learning_rate": c.learning_rate,
            "weight_decay": c.weight_decay,
            "min_variance": c.min_variance,
            "n_splits": c.n_splits,
            "seed": c.seed,
            "device": c.device,
        },
        "mean": trained.mean,
        "std": trained.std,
        "target_parameter": trained.target_parameter,
        "env_ids": list(trained.env_ids),
        "data_checksum": trained.data_checksum,
    }


def save_model(
    trained: TrainedModel,
    *,
    config_hash: str = "unknown",
    coverage: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    conformal: dict[str, Any] | None = None,
    artefacts_dir: Path | None = None,
    docs_dir: Path | None = None,
) -> dict[str, Path]:
    """Persist the model, its card sidecar, the human-readable doc card and a manifest.

    Returns the written paths. The card is generated from the model's own record so it
    always matches the artefact (§5).
    """
    from provenance.models.cards import write_doc_card

    directory = _artefacts_dir(artefacts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    record = trained.manifest(config_hash)
    record["parameter_count"] = trained.parameter_count
    card = build_card(record, coverage=coverage, baseline=baseline)

    model_path = directory / f"{trained.stem}{_MODEL_SUFFIX}"
    card_path = directory / f"{trained.stem}{_CARD_SUFFIX}"
    torch.save(_state_payload(trained, conformal), model_path)
    card_path.write_text(card.sidecar_json(), encoding="utf-8")

    resolved_docs = Path(docs_dir) if docs_dir is not None else get_settings().model_docs_dir
    doc_path = write_doc_card(card, resolved_docs)
    return {"model": model_path, "card": card_path, "doc": doc_path}


def _rebuild(payload: dict[str, Any]) -> LoadedModel:
    kind = str(payload["kind"])
    cfg_dict = dict(payload["config"])
    # Build the config through the same path the trainer uses.
    config = HSTGATConfig.from_config({"hstgat": cfg_dict})
    model = _KINDS[kind](config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return LoadedModel(
        kind=kind,
        model=model,
        config=config,
        mean=float(payload["mean"]),
        std=float(payload["std"]),
        target_parameter=str(payload["target_parameter"]),
        env_ids=list(payload["env_ids"]),
        data_checksum=str(payload["data_checksum"]),
        conformal=payload.get("conformal"),
    )


def load_artefact(stem: str, *, artefacts_dir: Path | None = None) -> LoadedModel:
    """Load one artefact by stem, enforcing a matching card (else raise).

    Refuses when the model or its card is absent, or when the card's checksum disagrees
    with the artefact — never returns an unverified model (§5).
    """
    directory = _artefacts_dir(artefacts_dir)
    model_path = directory / f"{stem}{_MODEL_SUFFIX}"
    card_path = directory / f"{stem}{_CARD_SUFFIX}"
    if not model_path.exists():
        raise ModelCardMissingError(f"No HST-GAT artefact at {model_path}.")
    if not card_path.exists():
        raise ModelCardMissingError(
            f"HST-GAT {stem!r} has no card sidecar ({card_path.name}); refusing to load a "
            "model whose provenance is unknown (§5). Retrain with `prov models train-hstgat`."
        )
    card_data: dict[str, Any] = json.loads(card_path.read_text(encoding="utf-8"))
    payload = torch.load(model_path, weights_only=False)
    if card_data.get("training_data_checksum") != payload.get("data_checksum"):
        raise ModelCardMissingError(
            f"Card for {stem!r} does not match the artefact: card checksum "
            f"{card_data.get('training_data_checksum')!r} != model checksum "
            f"{payload.get('data_checksum')!r}."
        )
    return _rebuild(payload)


def latest_stem(name: str = "hst-gat", *, artefacts_dir: Path | None = None) -> str | None:
    """The most recent versioned stem for ``name``, or ``None`` if none exist."""
    directory = _artefacts_dir(artefacts_dir)
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(f"{name}-*{_MODEL_SUFFIX}"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    return candidates[-1].name[: -len(_MODEL_SUFFIX)]


def load_latest(name: str = "hst-gat", *, artefacts_dir: Path | None = None) -> LoadedModel | None:
    """Load the latest artefact for ``name``, or ``None`` if absent (graceful degradation).

    Returns ``None`` for a *missing* model; raises :class:`ModelCardMissingError` only
    when an artefact is present but its card is not — a corrupt store, not an empty one.
    """
    stem = latest_stem(name, artefacts_dir=artefacts_dir)
    if stem is None:
        return None
    return load_artefact(stem, artefacts_dir=artefacts_dir)


_LATEST_CACHE: dict[tuple[str, Path], LoadedModel] = {}
"""Process-local cache of loaded HST-GAT artefacts, keyed by (name, resolved directory).

Same reasoning as :data:`provenance.models.registry._BUNDLE_CACHE`, and deliberately not
:func:`functools.lru_cache` for the same reason: absence is a normal state here, and a
cached ``None`` would keep the adjudicator on the analytic prior for the life of the
process even after a model was trained. Only a successful load is remembered.
"""


def load_latest_cached(
    name: str = "hst-gat", *, artefacts_dir: Path | None = None
) -> LoadedModel | None:
    """:func:`load_latest`, deserialising each artefact from disk at most once.

    Same contract as the uncached call: ``None`` when the artefact is absent, and
    :class:`ModelCardMissingError` when it is present but its card is not. Absence is
    never cached, so a later call still picks up a model that has since been trained.

    The API warms this at startup (``api/app.py``), so request paths do not pay the load.
    """
    key = (name, _artefacts_dir(artefacts_dir))
    cached = _LATEST_CACHE.get(key)
    if cached is not None:
        return cached
    loaded = load_latest(name, artefacts_dir=artefacts_dir)
    if loaded is not None:
        _LATEST_CACHE[key] = loaded
    return loaded
