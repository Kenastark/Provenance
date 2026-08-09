"""Feature provenance: where every model input actually came from.

A model card that lists ``temperature`` as a feature without saying it was a proxy,
not a measurement, is dishonest by omission. This module makes provenance a
first-class property of every feature column, so the card is generated from ground
truth rather than written from memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FeatureProvenance(StrEnum):
    """Where a feature column's values come from. Ordered least-to-most caveated."""

    MEASURED = "measured"
    """Read directly from the network's own in-situ sensors (confirmed parameters)."""

    DERIVED = "derived"
    """A deterministic function of the timestamp (hour, day-of-week, season). No
    external source and no uncertainty — the calendar is not a measurement."""

    WEATHER_FEED = "weather_feed"
    """From the HungaroMet covariate feed. Unavailable until its schema is confirmed
    (``schema_assumptions.yaml``: ``weather``); the column is imputed and flagged."""

    PROXY = "proxy"
    """A documented stand-in for a field we cannot measure yet — the boundary-layer
    height proxy (§5.3). Physically motivated, explicitly not the real quantity."""

    TRAFFIC = "traffic"
    """From the repaired Enclod counters. Unconfirmed schema (ADR 0003); imputed and
    flagged until the counter columns are read."""


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """One feature column: its name, where it came from, and why it is here."""

    name: str
    provenance: FeatureProvenance
    note: str
    available: bool = True
    """False when the source feed is unconfirmed, so the column is a flagged
    placeholder (imputed to a constant) rather than a real signal. The model card
    lists these explicitly so no one mistakes an imputed zero for a measurement."""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "provenance": self.provenance.value,
            "note": self.note,
            "available": self.available,
        }


@dataclass(frozen=True, slots=True)
class FeatureSet:
    """The feature matrix's column contract: names in order, each with provenance.

    Carried alongside the matrix everywhere so the deweather and fault models, the
    SHAP explainer, and the model card all speak the same stable column names — the
    "stable feature-name mapping" the explainability spec requires (§8).
    """

    specs: tuple[FeatureSpec, ...] = field(default_factory=tuple)

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.specs]

    @property
    def available_names(self) -> list[str]:
        """Columns backed by a real source — what a model should actually train on."""
        return [s.name for s in self.specs if s.available]

    def spec_for(self, name: str) -> FeatureSpec:
        for s in self.specs:
            if s.name == name:
                return s
        raise KeyError(f"No feature named {name!r}. Known: {', '.join(self.names)}")

    def to_dict(self) -> dict[str, object]:
        return {"features": [s.to_dict() for s in self.specs]}
