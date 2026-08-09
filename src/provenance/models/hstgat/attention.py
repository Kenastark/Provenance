"""Export per-prediction attention as weighted edges — "who influenced this call" (§8).

The whole point of putting attention on top of the graph is that it is *inspectable*:
for a given hour, the model's attention over each destination station's incoming edges
says which neighbours it actually leaned on. This module reads those weights out of a
forward pass and shapes them for the network map — a list of highlighted edges with an
``attention`` weight per edge, and a per-station ranking of its top influencers.

It is a read-out, not a claim: no accuracy, no verdict here (standing rule 4), just the
attention the model placed, rendered so a human can see the downwind neighbours light up
and judge for themselves whether the model looked where a plume would actually go.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from provenance.graph.snapshot import EdgeType
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField
from provenance.models.hstgat.data import build_batch
from provenance.models.hstgat.store import LoadedModel

# The relations worth drawing: the env↔env ones a plume actually rides.
_OVERLAY_RELATIONS = (EdgeType.WIND_CONDITIONED, EdgeType.SPATIAL_PROXIMITY)


def attention_overlay(
    loaded: LoadedModel,
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    at_time: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """Attention-weighted edges at ``at_time`` (default: the last hour), for the map.

    Returns a JSON-safe dict: per-relation edges ``{src, dst, attention, edge_weight}``
    and, per destination station, its top influencing neighbours by attention.
    """
    import torch

    batch = build_batch(
        frame,
        points,
        wind,
        cfg,
        target_parameter=loaded.target_parameter,
        mean=loaded.mean,
        std=loaded.std,
    )
    # Default to the last hour; if a specific hour is asked for but the target parameter
    # was not measured then, fall back to the last hour rather than crashing.
    if at_time is None:
        t = batch.n_times - 1
    else:
        want = pd.Timestamp(at_time)
        t = batch.times.index(want) if want in batch.times else batch.n_times - 1
    value_input = batch.target.clone()
    mask_flag = torch.zeros_like(batch.target)
    with torch.no_grad():
        fc = loaded.model(value_input, mask_flag, batch, return_attention_step=t)

    ids = batch.env_ids
    relations: dict[str, list[dict[str, Any]]] = {}
    influence: dict[str, list[dict[str, Any]]] = {}
    for edge_type in _OVERLAY_RELATIONS:
        att = fc.attention.get(edge_type)
        if att is None:
            continue
        edge_index, alpha = att
        rel = batch.relations[edge_type]
        wind_w = rel.wind_weight[t] if rel.wind_weight is not None else rel.static_weight
        edges: list[dict[str, Any]] = []
        for e in range(edge_index.shape[1]):
            src_i = int(edge_index[0, e])
            dst_i = int(edge_index[1, e])
            if src_i >= len(ids) or dst_i >= len(ids):
                continue
            a = float(alpha[e])
            w = float(wind_w[e]) if e < len(wind_w) else 0.0
            edges.append(
                {
                    "src": ids[src_i],
                    "dst": ids[dst_i],
                    "attention": round(a, 6),
                    "edge_weight": round(w, 6),
                }
            )
            influence.setdefault(ids[dst_i], []).append(
                {"neighbour": ids[src_i], "attention": round(a, 6), "relation": edge_type.value}
            )
        edges.sort(key=lambda x: (-x["attention"], x["src"], x["dst"]))
        relations[edge_type.value] = edges

    for dst in influence:
        influence[dst].sort(key=lambda x: (-x["attention"], x["neighbour"]))

    overlay: dict[str, Any] = {
        "at": batch.times[t].isoformat(),
        "target_parameter": loaded.target_parameter,
        "relations": relations,
        "influence": influence,
        "note": "Attention weights over each station's incoming edges — which neighbours "
        "the model leaned on. Not an accuracy figure (standing rule 4).",
    }
    return overlay


def write_overlay(overlay: dict[str, Any], out_path: Path) -> Path:
    """Write an attention overlay to JSON (deterministic: sorted keys, trailing newline)."""
    import json

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(overlay, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out_path


def write_overlay_for_drop(
    frame: pd.DataFrame,
    points: list[StationPoint],
    wind: WindField,
    cfg: dict[str, Any],
    out_dir: Path,
    *,
    at_time: pd.Timestamp | None = None,
    artefacts_dir: Path | None = None,
) -> Path | None:
    """Produce and write the attention overlay for a data drop, or ``None`` if no model.

    This is the reachable, product-flow entry point (the CLI's ``graph adjudicate
    --learned`` calls it): it loads the latest HST-GAT, builds the overlay, and writes
    ``out_dir/attention_overlay.json``. With no artefact it returns ``None`` rather than
    raising — a missing model degrades gracefully (standing rule 6).
    """
    from provenance.models.hstgat.store import load_latest

    loaded = load_latest(artefacts_dir=artefacts_dir)
    if loaded is None:
        return None
    overlay = attention_overlay(loaded, frame, points, wind, cfg, at_time=at_time)
    return write_overlay(overlay, Path(out_dir) / "attention_overlay.json")
