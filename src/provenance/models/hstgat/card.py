"""Build the HST-GAT's model card from its own training record.

Reuses the phase-5 :class:`~provenance.models.cards.ModelCard` machinery so the neural
model is described by exactly the same kind of card the tree models are (§5): generated
from the record, never hand-typed to drift from what was trained. The honesty rails
specific to this model live here — the small-data justification for the parameter count
(§5.1), the achieved conformal coverage (§7.7), the GCN-baseline comparison, and the
standing-rule-4 refusal to quote a propagation accuracy figure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from provenance.models.cards import ModelCard


def build_card(
    record: dict[str, Any],
    *,
    coverage: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
) -> ModelCard:
    """Assemble the HST-GAT card from a trained model's manifest ``record``.

    ``coverage`` is the achieved split-conformal coverage (or ``None`` if not yet
    calibrated); ``baseline`` is the GCN baseline's held-out metrics for comparison.
    """
    param_count = int(record["parameter_count"])
    n_train = int(record.get("n_timesteps", 720))
    features = [
        {
            "name": "EnvStation.value",
            "provenance": "measured (target parameter)",
            "note": "reconstruction target",
        },
        {
            "name": "EnvStation.wind",
            "provenance": "measured / city-fallback",
            "note": "sin/cos(from), saturated speed",
        },
        {
            "name": "spatial_proximity edge",
            "provenance": "geometry",
            "note": "static inverse-distance",
        },
        {
            "name": "wind_conditioned edge",
            "provenance": "geometry + wind(t)",
            "note": "additive attention bias",
        },
        {
            "name": "weather_influence edge",
            "provenance": "city wind broadcast",
            "note": "weather node → env",
        },
        {
            "name": "road_adjacency / transit_corridor edge",
            "provenance": "placeholder (ADR 0003)",
            "note": "structural only; Enclod/GTFS unconfirmed, learned type embedding",
        },
    ]
    limitations = [
        "No headline accuracy or F1 is reported for the propagation validator (standing "
        "rule 4, §16 critique 2): with this few real corroborated events such a number "
        "would describe the synthetic injection process, not the world. The metrics here "
        "are the masked-reconstruction NLL/RMSE of the imputation task, which describe the "
        "model, plus per-case evidence and calibrated intervals in the adjudication bundle.",
        f"Deliberately small: {param_count} parameters against ~{n_train} timesteps per "
        "station (§5.1). A larger model would memorise this corpus rather than learn "
        "propagation; capacity is spent on structure (heterogeneous attention, a per-station "
        "GRU) rather than width. Trained forward-chaining only — no random K-fold on a time "
        "series (standing rule 7).",
        "The auxiliary node types (TrafficCounter, BusStop, WeatherNode) carry no confirmed "
        "time-varying measurements yet (Enclod/GTFS unconfirmed, ADR 0003); their attention "
        "heads are architecturally present but data-limited, represented by learned "
        "placeholder embeddings, never invented signal (standing rule 2).",
        "Determinism is guaranteed on CPU (ADR 0009); an MPS/GPU run may differ in the last "
        "bits and is opt-in.",
    ]
    extra: dict[str, Any] = {
        "parameter_count": param_count,
        "wind_bias": "additive pre-softmax; beta=0 recovers a plain HetGAT (tested)",
        "target_parameter": record.get("target_parameter"),
        "git_sha": record.get("git_sha"),
        "seed": record.get("seed"),
    }
    if baseline is not None:
        extra["gcn_baseline"] = baseline
    if coverage is not None:
        extra["conformal_coverage"] = coverage

    return ModelCard(
        name=str(record.get("name", "hst-gat")),
        version=str(record["version"]),
        kind="hstgat",
        training_data_checksum=str(record["data_checksum"]),
        window_start=str(record.get("window_start", "")),
        window_end=str(record.get("window_end", "")),
        cv_scheme="time-blocked forward-chaining (masked-autoencoder reconstruction)",
        features=features,
        metrics=dict(record.get("metrics", {})),
        limitations=limitations,
        extra=extra,
        generated_at=datetime.now(UTC).isoformat(),
    )
