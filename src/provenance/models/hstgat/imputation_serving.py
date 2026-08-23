"""Serve the trained per-parameter imputation models to the trust engine (§7.2/§7.8).

One artefact per parameter (see ``prov models train-imputation``), same ``HSTGAT``
class and masked-AE mechanism as the fault-adjudication model, distinguished only by
artefact name (``imputation-<PARAMETER>``). This module is the thin serving seam: find
what is trained, and turn its predicted uncertainty into a bounded [0, 1) figure the
trust score's ``(1 - ImputationUncertainty)`` term can consume.

Graceful degradation (standing rule 6): a parameter with no trained artefact, or a
station/hour the model cannot forecast, contributes nothing here — the caller falls
back to the raw absent-fraction placeholder for that station, exactly as before this
model existed.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.models.hstgat.data import TemporalGraphBatch
from provenance.models.hstgat.store import LoadedModel, load_latest
from provenance.models.registry import ModelCardMissingError

ARTEFACT_PREFIX = "imputation"


def artefact_name(parameter: str) -> str:
    return f"{ARTEFACT_PREFIX}-{parameter}"


def available_imputation_models(
    parameters: list[str],
    *,
    data_checksum: str,
    artefacts_dir: Path | None = None,
) -> dict[str, LoadedModel]:
    """The latest, card-verified imputation artefact per parameter, for THIS drop.

    ``data_checksum`` is the content checksum of the frame being scored
    (:func:`provenance.schema.observe.observe`). An artefact is used only when its
    own ``data_checksum`` matches: the artefact store keeps only one file per
    parameter name regardless of which drop trained it, so without this check a
    model trained on one corpus (e.g. the real Green Sentinel drop) would silently
    run inference against a different one sharing the same parameter vocabulary
    (e.g. the synthetic demo corpus, whose station graph the model never saw) and
    produce a plausible-looking but meaningless number. A parameter with no
    artefact, a stale/mismatched one, or one whose card does not verify is silently
    omitted rather than raising — the caller degrades to the placeholder for
    exactly that parameter, not the whole load.
    """
    out: dict[str, LoadedModel] = {}
    for p in parameters:
        try:
            loaded = load_latest(name=artefact_name(p), artefacts_dir=artefacts_dir)
        except ModelCardMissingError:
            continue
        if loaded is not None and loaded.data_checksum == data_checksum:
            out[p] = loaded
    return out


def sigma_to_uncertainty(sigma_std: float) -> float:
    """Map a standardised-space predicted sigma to a bounded [0, 1) uncertainty.

    ``sigma_std`` is already scale-free (the model predicts variance in the target's
    standardised units), so ``tanh`` gives a smooth, monotonic squash with no extra
    fitted constant: 0 when the model is confident, approaching 1 as sigma reaches or
    exceeds a full standard deviation of the parameter's natural variation. This is
    the figure that feeds the Trust Score's ``(1 - ImputationUncertainty)`` term
    (§7.8) once a model is available.
    """
    return float(math.tanh(max(sigma_std, 0.0)))


def build_imputation_batch(
    loaded: LoadedModel,
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
) -> TemporalGraphBatch:
    """The tensorised graph for ``loaded``'s parameter, built once per load.

    A load scores every station at up to ~120 instants (§7.8's scoring cadence); the
    caller builds this batch once per parameter and reuses it across all of them via
    :func:`sigma_at`, instead of rebuilding the graph for every hour scored — the
    difference between one graph build per parameter and up to ~120.
    """
    from provenance.models.hstgat.data import build_batch

    return build_batch(
        frame,
        points,
        wind,
        cfg,
        target_parameter=loaded.target_parameter,
        mean=loaded.mean,
        std=loaded.std,
    )


def sigma_at(loaded: LoadedModel, batch: TemporalGraphBatch, at: pd.Timestamp) -> dict[str, float]:
    """Per-station modelled uncertainty in [0, 1) for ``loaded``'s parameter at ``at``.

    Same masked-AE mechanism as
    :func:`provenance.models.hstgat.forecast.forecast_at_hour` (hide every station's
    reading at ``at``, reconstruct mean + sigma from the wind-weighted neighbours),
    but against a batch the caller already built (:func:`build_imputation_batch`)
    rather than rebuilding it for every hour scored.
    """
    import torch

    if at not in batch.times:
        return {}
    t = batch.times.index(at)
    hidden = torch.zeros_like(batch.target, dtype=torch.bool)
    hidden[t] = batch.observed[t]
    value_input = torch.where(hidden, torch.zeros_like(batch.target), batch.target)
    mask_flag = hidden.to(batch.target.dtype)
    with torch.no_grad():
        fc = loaded.model(value_input, mask_flag, batch, return_attention_step=t)
    sigma_std = torch.sqrt(fc.variance[t]).numpy()
    return {sid: sigma_to_uncertainty(float(sigma_std[i])) for i, sid in enumerate(batch.env_ids)}
