"""The Alert Centre: rank candidate alerts by RISK, not by trust or confidence (§9.5).

The distinction is the whole point of the layer. A *sensor fault* — however confident
the adjudicator is that it is a fault — is a data-quality problem: it belongs in the
maintenance queue, and its public-health risk is near zero because the alarming number
is not real. A *genuine event* is a public-health risk that scales with how many
people are exposed. So the Alert Centre must be able to put a high-confidence,
high-exposure genuine event **above** a high-confidence, low-exposure sensor fault,
even though the fault is the more certain classification.

Risk here is therefore consequence-weighted, not certainty-weighted::

    risk = genuineness × exposure × hazard × (0.5 + 0.5·confidence)

* ``genuineness`` collapses a confident *fault* toward zero (a fault is not a public
  hazard) while a genuine event keeps its full weight;
* ``exposure`` is the PopulationExposure factor from the GTFS transit-corridor layer;
* ``hazard`` is how dangerous the reading would be *if real* (severity, normalised);
* ``confidence`` modulates but never dominates — two equally confident alerts still
  separate on genuineness and exposure, which is what the ranking test pins.

Every ranked alert carries its risk breakdown, so the Alert Centre never shows a bare
number (standing rule 9, extended to risk).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from provenance.ops.severity import hazard as _hazard

# How much of its risk a verdict keeps. A confirmed fault is a maintenance issue, not
# a public hazard, so it is collapsed hard; an unadjudicated candidate is treated as
# ambiguous rather than assumed genuine.
GENUINENESS: dict[str, float] = {
    "GENUINE_EVENT": 1.0,
    "AMBIGUOUS": 0.5,
    "LIKELY_FAULT": 0.15,
}
_UNADJUDICATED_GENUINENESS = 0.5


@dataclass(frozen=True, slots=True)
class AlertCandidate:
    """A candidate for the Alert Centre, before it is scored and ranked."""

    event_id: int
    station_id: str
    parameter: str
    severity: str
    verdict: str | None
    confidence: float
    exposure: float
    headline: str
    timestamp_utc: str

    @property
    def genuineness(self) -> float:
        if self.verdict is None:
            return _UNADJUDICATED_GENUINENESS
        return GENUINENESS.get(self.verdict, _UNADJUDICATED_GENUINENESS)


@dataclass(frozen=True, slots=True)
class RankedAlert:
    """A scored alert with the factors that produced its risk — never a bare number."""

    candidate: AlertCandidate
    risk: float
    factors: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        c = self.candidate
        return {
            "event_id": c.event_id,
            "station_id": c.station_id,
            "parameter": c.parameter,
            "severity": c.severity,
            "verdict": c.verdict,
            "confidence": round(c.confidence, 6),
            "exposure": round(c.exposure, 6),
            "headline": c.headline,
            "timestamp_utc": c.timestamp_utc,
            "risk": round(self.risk, 6),
            "risk_factors": {k: round(v, 6) for k, v in self.factors.items()},
        }


def alert_risk(candidate: AlertCandidate) -> RankedAlert:
    """Score one candidate. Consequence-weighted, so a fault cannot outrank an event."""
    genuineness = candidate.genuineness
    exposure = float(candidate.exposure)
    hz = _hazard(candidate.severity)
    conf_weight = 0.5 + 0.5 * float(candidate.confidence)
    risk = genuineness * exposure * hz * conf_weight
    return RankedAlert(
        candidate=candidate,
        risk=risk,
        factors={
            "genuineness": genuineness,
            "exposure": exposure,
            "hazard": hz,
            "confidence_weight": conf_weight,
        },
    )


def rank_alerts(candidates: list[AlertCandidate]) -> list[RankedAlert]:
    """Score and order candidates by risk, descending.

    The tiebreak is deterministic — higher exposure, then lower (more recent-sorting)
    event id — so two runs over the same candidates return byte-identical order
    (standing rule 8).
    """
    scored = [alert_risk(c) for c in candidates]
    scored.sort(key=lambda a: (-a.risk, -a.candidate.exposure, a.candidate.event_id))
    return scored
