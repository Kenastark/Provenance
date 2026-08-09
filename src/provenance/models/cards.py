"""Model cards: a model is not allowed to exist without one.

Every trained model auto-generates a card (§5) describing its data window, its
features *with provenance*, its CV scheme, its metrics, its class balance, its known
limitations and the checksum of the data it was trained on. Two copies are written:

* a human-readable Markdown card under ``docs/model-cards/`` (versioned, never edited
  in place — the filename carries the data checksum, standing rule 10);
* a machine-readable JSON sidecar next to the artefact, which the registry checks on
  load. A model whose sidecar is missing or whose checksum disagrees with the artefact
  will not load (§5, enforced in :mod:`provenance.models.registry`).

The card is generated *from the model's own record*, so it cannot describe a model
that does not exist or claim a metric the model did not measure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelCard:
    """The provenance record for one trained model."""

    name: str  # "deweather" | "fault"
    version: str
    kind: str
    training_data_checksum: str
    window_start: str
    window_end: str
    cv_scheme: str
    features: list[dict[str, Any]]
    metrics: dict[str, Any]
    limitations: list[str]
    extra: dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""

    @property
    def stem(self) -> str:
        """The versioned filename stem shared by the artefact, sidecar and doc card."""
        return f"{self.name}-{self.version}"

    def integrity_dict(self) -> dict[str, Any]:
        """The load-time integrity payload — deliberately excludes ``generated_at``.

        The checksum that gates loading must be stable across two trainings on the same
        data; a wall-clock timestamp would make it non-deterministic (standing rule 8),
        so it is carried for humans but not part of what the registry verifies.
        """
        return {
            "name": self.name,
            "version": self.version,
            "kind": self.kind,
            "training_data_checksum": self.training_data_checksum,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "cv_scheme": self.cv_scheme,
            "features": self.features,
            "metrics": self.metrics,
            "limitations": self.limitations,
            "extra": self.extra,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.integrity_dict(), "generated_at": self.generated_at}

    def sidecar_json(self) -> str:
        return (
            json.dumps(self.integrity_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )


def deweather_card(model: Any) -> ModelCard:
    """Build the card for a :class:`DeweatherModel`."""
    d = model.to_card_dict()
    limitations = [
        "R² is reported as a sanity band (0.15-0.90), not a performance claim: too low "
        "means weather is not captured, too high means no genuine signal is left to find.",
        "Trained forward-chaining only (time-blocked CV); no random K-fold on this time "
        "series (standing rule 7).",
    ]
    if not d["weather_available"]:
        limitations.append(
            "The HungaroMet feed was unconfirmed at training: temperature and "
            "precipitation were imputed constants, flagged in the feature list (§5.3)."
        )
    return ModelCard(
        name="deweather",
        version=d["version"],
        kind="deweather",
        training_data_checksum=d["data_checksum"],
        window_start=d["window_start"],
        window_end=d["window_end"],
        cv_scheme=f"time-blocked forward-chaining, {d['n_splits']} folds",
        features=d["features"],
        metrics=d["metrics"],
        limitations=limitations,
        extra={"pollutants": d["pollutants"], "weather_available": d["weather_available"]},
        generated_at=datetime.now(UTC).isoformat(),
    )


def fault_card(model: Any) -> ModelCard:
    """Build the card for a :class:`FaultClassifier`."""
    d = model.to_card_dict()
    limitations = [
        "No headline accuracy figure is reported (standing rule 4): with this few real "
        "positives, one would describe the synthetic injection process, not the world.",
        "Deterministic rules decide the physical/frozen/comms/unit classes and are "
        "excluded from the learned confusion matrix; the ML only chooses among the three "
        "subtle classes.",
        "meteorological_artefact is watched hardest: mislabelling a real inversion as a "
        f"fault is the most damaging error this system makes. Precision floor "
        f"{d['meteorological_artefact_precision_floor']}.",
    ]
    return ModelCard(
        name="fault",
        version=d["version"],
        kind="fault",
        training_data_checksum=d["data_checksum"],
        window_start=d["window_start"],
        window_end=d["window_end"],
        cv_scheme=f"time-blocked forward-chaining, {d['n_splits']} folds",
        features=[{"name": f, "provenance": "residual-derived"} for f in d["features"]],
        metrics={"per_class": d["per_class"], "signature_recall": d["signature_recall"]},
        limitations=limitations,
        extra={
            "classes": d["classes"],
            "ml_classes": d["ml_classes"],
            "confusion_matrix": d["confusion_matrix"],
            "recall_floors": d["recall_floors"],
            "meteorological_artefact_precision": d["meteorological_artefact_precision"],
            "meteorological_artefact_precision_floor": d["meteorological_artefact_precision_floor"],
        },
        generated_at=datetime.now(UTC).isoformat(),
    )


def render_markdown(card: ModelCard) -> str:
    """Render a human-readable Markdown model card."""
    lines: list[str] = [
        f"# Model card — {card.name} `{card.version}`",
        "",
        f"*Generated {card.generated_at}. Kind: {card.kind}.*",
        "",
        "## Data",
        "",
        f"- Training window: `{card.window_start}` → `{card.window_end}`",
        f"- Training-data checksum: `{card.training_data_checksum}`",
        f"- Cross-validation: {card.cv_scheme}",
        "",
        "## Features",
        "",
        "| Feature | Provenance | Available | Note |",
        "| --- | --- | --- | --- |",
    ]
    for f in card.features:
        lines.append(
            f"| `{f.get('name', '')}` | {f.get('provenance', '')} | "
            f"{f.get('available', True)} | {f.get('note', '')} |"
        )
    lines += [
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(card.metrics, indent=2, sort_keys=True),
        "```",
        "",
    ]
    if card.extra:
        lines += [
            "## Details",
            "",
            "```json",
            json.dumps(card.extra, indent=2, sort_keys=True),
            "```",
            "",
        ]
    lines += ["## Known limitations", ""]
    lines += [f"- {limit}" for limit in card.limitations]
    lines.append("")
    return "\n".join(lines)


def write_doc_card(card: ModelCard, docs_dir: Path) -> Path:
    """Write the human-readable card to ``docs/model-cards/<name>-<version>.md``."""
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{card.stem}.md"
    path.write_text(render_markdown(card), encoding="utf-8")
    return path
