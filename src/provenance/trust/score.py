"""The trust score value object — a number that cannot exist without its reasons.

:class:`TrustScore` refuses to construct without a component breakdown and at
least one reason code (standing rule 9). That invariant lives in the value
object, not in a serialiser, so no code path anywhere — API, CLI, or storage —
can produce a bare score: to have a ``TrustScore`` at all is to have its reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TrustComponent:
    """One weighted term of the trust score, with its contribution shown."""

    name: str
    value: float
    weight: float
    is_placeholder: bool = False
    """True for terms that are not yet backed by a calibrated model (imputation)."""
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    """The figures behind this term, keyed by the placeholder names the reason-code
    sentences use.

    ``detail`` is prose for a human; this is the same information in a form a
    renderer can substitute. Keeping only the prose is what made the dashboard show
    "Trust is reduced by disagreement with — neighbouring station(s)": the engine
    had counted the neighbours and then thrown the count away."""

    @property
    def contribution(self) -> float:
        return round(self.value * self.weight, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 6),
            "weight": self.weight,
            "contribution": self.contribution,
            "is_placeholder": self.is_placeholder,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class Risk:
    """Risk = Trust x SeverityVsThreshold x PopulationExposure (§7.8).

    ``population_exposure_stubbed`` is carried, never silently defaulted: the
    consumer must be told the exposure factor is a stub until GTFS lands.
    """

    value: float
    trust: float
    severity_vs_threshold: float
    population_exposure: float
    population_exposure_stubbed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": round(self.value, 6),
            "trust": round(self.trust, 6),
            "severity_vs_threshold": round(self.severity_vs_threshold, 6),
            "population_exposure": round(self.population_exposure, 6),
            "population_exposure_stubbed": self.population_exposure_stubbed,
        }


@dataclass(frozen=True, slots=True)
class TrustScore:
    """A trust score at a point in time, inseparable from its explanation."""

    station_id: str
    timestamp_utc: str
    value: float
    components: list[TrustComponent]
    reason_codes: list[str]
    risk: Risk
    degraded: bool = False
    """True when a model artefact was missing and the score came from statistics
    alone (graceful degradation, standing rule 6)."""
    notes: list[str] = field(default_factory=list)

    @property
    def evidence(self) -> dict[str, Any]:
        """Every component's figures, merged — the substitution map for a sentence.

        The merge assumes the components' evidence keys are pairwise disjoint: each
        key is a placeholder name owned by exactly one component, so no component can
        silently overwrite another's figure. That invariant is a property of the
        component code, not of the data — only a code change could break it — so it
        is pinned by ``tests/unit/test_trust_reason_evidence.py`` rather than by a
        runtime check here. A guard in this hot path (it runs per station per scoring
        instant) would risk taking a whole score down over what is, at worst, a
        cosmetic label collision; the test catches it in CI instead, before it ships.
        """
        merged: dict[str, Any] = {}
        for component in self.components:
            merged.update(component.evidence)
        return merged

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("a trust score cannot render without its component breakdown")
        if not self.reason_codes:
            raise ValueError("a trust score cannot render without at least one reason code")
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"trust value {self.value} is outside [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "timestamp_utc": self.timestamp_utc,
            "trust": round(self.value, 6),
            "components": [c.to_dict() for c in self.components],
            "reason_codes": list(self.reason_codes),
            "risk": self.risk.to_dict(),
            "degraded": self.degraded,
            "notes": list(self.notes),
            "evidence": self.evidence,
        }
