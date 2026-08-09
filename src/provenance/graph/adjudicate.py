"""The propagation adjudicator: plume, fault, or (first-class) ambiguous.

Given a candidate event — a rise at station *i* the audit flagged as notable — this
asks the one question the statistics layer cannot: *did the rest of the network see
it too, where and when a plume should have carried it?* A real emission plume rides
the wind and lights up downwind neighbours with an attenuated, delayed echo. A stuck
or spiking sensor does not: it rises alone, contradicting neighbours that stayed
flat.

The verdict is one of three, and **AMBIGUOUS is designed, not a failure** (§7.5): a
partially corroborated event, or one with too few downwind neighbours to judge, is
routed to a human rather than forced into a binary. That routing is a first-class
outcome the type system and the UI both treat as such.

Honesty rails, load-bearing here:

* No headline accuracy figure is produced (standing rule 4, §16 critique 2). There
  are too few real corroborated events to make one mean anything; this returns
  per-case evidence, not a score for the method.
* The traffic and weather covariates are **stubs** in this phase — Enclod is
  unconfirmed and deweathering is phase 5 — and they say so in the bundle rather than
  quietly reading as "no explanation found".
* The adjudicator is not a detector: its reason codes never enter the defect rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

from provenance.graph.edges import WindEdgeParams, wind_edge_weight
from provenance.graph.expectation import (
    AnalyticExpectation,
    ExpectationProvider,
)
from provenance.graph.propagation import (
    PropagationParams,
    evaluation_hours,
)
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindField, WindProvenance, WindVector
from provenance.schema import canonical as C


class Verdict(StrEnum):
    """The three adjudication outcomes. AMBIGUOUS is first-class (§7.5)."""

    GENUINE_EVENT = "GENUINE_EVENT"
    LIKELY_FAULT = "LIKELY_FAULT"
    AMBIGUOUS = "AMBIGUOUS"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


# Reason codes the adjudicator surfaces (from the registry; never defect-rate flags).
RC_GENUINE = "R22"
RC_FAULT = "R17"
RC_AMBIGUOUS = "R23"


@dataclass(frozen=True, slots=True)
class CandidateEvent:
    """A candidate event to adjudicate: a rise at one station, above its own baseline."""

    station_id: str
    parameter: str
    timestamp: pd.Timestamp
    value: float
    baseline: float
    anomaly_score: float = 0.0
    unit: str = ""

    @property
    def excess(self) -> float:
        return self.value - self.baseline

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "parameter": self.parameter,
            "timestamp_utc": pd.Timestamp(self.timestamp).isoformat(),
            "value": round(self.value, 4),
            "baseline": round(self.baseline, 4),
            "excess": round(self.excess, 4),
            "anomaly_score": round(self.anomaly_score, 4),
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class NeighbourEvidence:
    """One downwind neighbour's expected-vs-actual comparison."""

    station_id: str
    distance_km: float
    bearing_deg: float
    edge_weight: float
    wind_provenance: str
    carries_parameter: bool
    arrival_delay_min: float
    expected_excess: float
    actual_excess: float | None
    corroborated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_id": self.station_id,
            "distance_km": round(self.distance_km, 4),
            "bearing_deg": round(self.bearing_deg, 2),
            "edge_weight": round(self.edge_weight, 6),
            "wind_provenance": self.wind_provenance,
            "carries_parameter": self.carries_parameter,
            "arrival_delay_min": round(self.arrival_delay_min, 2),
            "expected_excess": round(self.expected_excess, 4),
            "actual_excess": None if self.actual_excess is None else round(self.actual_excess, 4),
            "corroborated": self.corroborated,
        }


@dataclass(frozen=True, slots=True)
class CovariateState:
    """The state of a covariate the adjudicator would like to consult but cannot yet."""

    name: str
    state: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class ExpectedActualSeries:
    """The overlaid expected and actual downwind series the dashboard draws."""

    timestamps: list[str]
    expected: list[float]
    actual: list[float | None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamps": self.timestamps,
            "expected": [round(v, 4) for v in self.expected],
            "actual": [None if v is None else round(v, 4) for v in self.actual],
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Everything the adjudicator looked at, so a human can re-run the judgement by eye."""

    wind: dict[str, Any]
    downwind_neighbours: list[NeighbourEvidence]
    series: ExpectedActualSeries
    match_score: float
    n_downwind: int
    n_usable: int
    covariates: list[CovariateState]
    reason_codes: list[str]
    notes: list[str] = field(default_factory=list)
    expectation_provenance: str = "analytic"
    """Which expectation produced this verdict — "analytic" (phase-4 plume prior) or
    "hst-gat" (the learned forecast). Recorded so the fallback is always visible in the
    bundle a human reviews (standing rule 6), never silent."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "wind": self.wind,
            "downwind_neighbours": [n.to_dict() for n in self.downwind_neighbours],
            "series": self.series.to_dict(),
            "match_score": round(self.match_score, 4),
            "n_downwind": self.n_downwind,
            "n_usable": self.n_usable,
            "covariates": [c.to_dict() for c in self.covariates],
            "reason_codes": list(self.reason_codes),
            "notes": list(self.notes),
            "expectation_provenance": self.expectation_provenance,
        }


@dataclass(frozen=True, slots=True)
class Adjudication:
    """A verdict, its confidence, and the full evidence — inseparable by construction.

    Invariants enforced here rather than by a serialiser (§7.5):

    * AMBIGUOUS never renders as high confidence, and routes to human review.
    * GENUINE/FAULT do not route to review.
    * confidence is in [0, 1].
    """

    event: CandidateEvent
    verdict: Verdict
    confidence: float
    confidence_band: ConfidenceBand
    routes_to_review: bool
    evidence: EvidenceBundle

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence {self.confidence} is outside [0, 1]")
        if self.verdict is Verdict.AMBIGUOUS:
            if self.confidence_band is ConfidenceBand.HIGH:
                raise ValueError("an AMBIGUOUS verdict must never be presented as high confidence")
            if not self.routes_to_review:
                raise ValueError("an AMBIGUOUS verdict must route to human review")
        elif self.routes_to_review:
            raise ValueError("only an AMBIGUOUS verdict routes to human review")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.to_dict(),
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band.value,
            "routes_to_review": self.routes_to_review,
            "evidence": self.evidence.to_dict(),
        }


# --------------------------------------------------------------------------- config
@dataclass(frozen=True, slots=True)
class AdjudicatorParams:
    genuine_match_threshold: float
    fault_match_threshold: float
    min_downwind_neighbours: int
    corroboration_tolerance: float
    ambiguous_confidence_cap: float
    confidence_high_at: float
    confidence_moderate_at: float
    downwind_weight_floor: float
    baseline_window_hours: int

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> AdjudicatorParams:
        a = cfg["adjudicator"]
        return cls(
            genuine_match_threshold=float(a["genuine_match_threshold"]),
            fault_match_threshold=float(a["fault_match_threshold"]),
            min_downwind_neighbours=int(a["min_downwind_neighbours"]),
            corroboration_tolerance=float(a["corroboration_tolerance"]),
            ambiguous_confidence_cap=float(a["ambiguous_confidence_cap"]),
            confidence_high_at=float(a["confidence_high_at"]),
            confidence_moderate_at=float(a["confidence_moderate_at"]),
            downwind_weight_floor=float(a["downwind_weight_floor"]),
            baseline_window_hours=int(a["baseline_window_hours"]),
        )

    def band(self, confidence: float) -> ConfidenceBand:
        if confidence >= self.confidence_high_at:
            return ConfidenceBand.HIGH
        if confidence >= self.confidence_moderate_at:
            return ConfidenceBand.MODERATE
        return ConfidenceBand.LOW


def _series(readings: pd.DataFrame, station_id: str, parameter: str) -> pd.Series:
    rows = readings[(readings[C.STATION_ID] == station_id) & (readings[C.PARAMETER] == parameter)]
    if rows.empty:
        return pd.Series(dtype="float64")
    series = rows.set_index(C.TIMESTAMP)[C.VALUE].astype("float64").sort_index()
    return series[~series.index.duplicated(keep="last")]


def _baseline(series: pd.Series, before: pd.Timestamp, window_hours: int) -> float | None:
    if series.empty:
        return None
    window_start = before - pd.Timedelta(hours=window_hours)
    prior = series[(series.index >= window_start) & (series.index < before)]
    if prior.empty:
        prior = series[series.index < before]
    if prior.empty:
        return None
    return float(np.median(prior.to_numpy()))


def _value_at(series: pd.Series, hours: list[pd.Timestamp]) -> float | None:
    for ts in hours:
        if ts in series.index:
            return float(series.loc[ts])
    return None


def _covariate_stubs() -> list[CovariateState]:
    """The covariates the adjudicator would consult if their feeds were confirmed.

    Named and explained rather than silently omitted, so "no explanation found" is
    never mistaken for "explanation ruled out" (§16 critique 2, standing rule 2)."""
    return [
        CovariateState(
            name="traffic",
            state="unavailable",
            reason="Enclod counter schema is unconfirmed (ADR 0003); the traffic covariate "
            "lands once the columns are read. Until then it neither supports nor excuses a rise.",
        ),
        CovariateState(
            name="weather",
            state="wind-only",
            reason="Only the wind vector is used here. Boundary-layer height and full "
            "deweathering (the R20 meteo-artefact test) arrive in phase 5.",
        ),
    ]


def validate_event(
    event: CandidateEvent,
    points: list[StationPoint],
    wind: WindField,
    readings: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    expectation: ExpectationProvider | None = None,
) -> Adjudication:
    """Adjudicate one candidate event over the wind graph. Returns a full bundle.

    Deterministic in ``(event, geometry, wind at the event hour, readings, config)``.

    ``expectation`` chooses who computes the downwind expectation each neighbour is
    judged against: the default :class:`~provenance.graph.expectation.AnalyticExpectation`
    is the phase-4 plume prior (and reproduces phase-4 verdicts byte-for-byte), while a
    learned :class:`~provenance.graph.expectation.ExpectationProvider` injected from the
    ``models`` layer swaps in the HST-GAT forecast (§6.4). The adjudicator imports
    neither the model nor torch — the seam is a Protocol, so the layering holds. Which
    provider ran is recorded in the evidence bundle's ``expectation_provenance``.
    """
    params = AdjudicatorParams.from_config(cfg)
    wind_params = WindEdgeParams.from_config(cfg)
    prop_params = PropagationParams.from_config(cfg)
    provider: ExpectationProvider = (
        expectation if expectation is not None else AnalyticExpectation()
    )

    by_id = {p.station_id: p for p in points}
    source = by_id.get(event.station_id)
    vec = wind.at(event.timestamp, event.station_id) if source is not None else None

    covariates = _covariate_stubs()

    # No source geometry or no wind → the plume test cannot run: AMBIGUOUS, to review.
    if source is None or vec is None or vec.speed < wind_params.min_wind_speed:
        note = (
            "No wind vector at the event hour (calm or unmeasured); propagation cannot "
            "be assessed, so the event is routed to review rather than guessed."
            if source is not None
            else "The event's station has no coordinate in the graph; cannot assess propagation."
        )
        return _ambiguous_without_neighbours(
            event, vec, wind, covariates, note, params, provider.provenance
        )

    hours = evaluation_hours(event.timestamp, prop_params)
    neighbours: list[NeighbourEvidence] = []
    for p in points:
        if p.station_id == event.station_id:
            continue
        weight = wind_edge_weight(
            source.lat, source.lon, p.lat, p.lon, vec.from_deg, vec.speed, wind_params
        )
        if weight < params.downwind_weight_floor:
            continue
        exp = provider.expect(source, p, vec, event, wind_params, prop_params)
        n_series = _series(readings, p.station_id, event.parameter)
        carries = not n_series.empty
        actual_excess: float | None = None
        corroborated = False
        if carries:
            base = _baseline(n_series, event.timestamp, params.baseline_window_hours)
            actual = _value_at(n_series, hours)
            if base is not None and actual is not None:
                actual_excess = actual - base
                threshold = exp.expected_excess * (1.0 - params.corroboration_tolerance)
                corroborated = (
                    exp.within_horizon and exp.expected_excess > 0 and actual_excess >= threshold
                )
        neighbours.append(
            NeighbourEvidence(
                station_id=p.station_id,
                distance_km=exp.distance_km,
                bearing_deg=exp.bearing_deg,
                edge_weight=weight,
                wind_provenance=vec.provenance.value,
                carries_parameter=carries,
                arrival_delay_min=exp.arrival_delay_min,
                expected_excess=exp.expected_excess,
                actual_excess=actual_excess,
                corroborated=corroborated,
            )
        )

    neighbours.sort(key=lambda n: (-n.edge_weight, n.station_id))
    usable = [n for n in neighbours if n.carries_parameter and n.actual_excess is not None]
    match_score = _match_score(usable)
    series = _build_series(event, hours, usable)

    verdict, confidence = _decide(match_score, len(usable), params)
    reason_codes = _reason_codes_for(verdict)
    band = params.band(confidence)
    if verdict is Verdict.AMBIGUOUS:
        confidence = min(confidence, params.ambiguous_confidence_cap)
        band = params.band(confidence)
        if band is ConfidenceBand.HIGH:  # defensive; cap keeps us below high by config
            band = ConfidenceBand.MODERATE

    bundle = EvidenceBundle(
        wind=_wind_dict(vec, wind),
        downwind_neighbours=neighbours,
        series=series,
        match_score=match_score,
        n_downwind=len(neighbours),
        n_usable=len(usable),
        covariates=covariates,
        reason_codes=reason_codes,
        notes=_notes_for(verdict, len(usable), params),
        expectation_provenance=provider.provenance,
    )
    return Adjudication(
        event=event,
        verdict=verdict,
        confidence=round(confidence, 4),
        confidence_band=band,
        routes_to_review=verdict is Verdict.AMBIGUOUS,
        evidence=bundle,
    )


def _decide(match_score: float, n_usable: int, params: AdjudicatorParams) -> tuple[Verdict, float]:
    """Map corroboration + neighbour count to a verdict and a confidence in [0, 1]."""
    if n_usable < params.min_downwind_neighbours:
        # Too few downwind neighbours to corroborate either way.
        return Verdict.AMBIGUOUS, params.ambiguous_confidence_cap
    if match_score >= params.genuine_match_threshold:
        return Verdict.GENUINE_EVENT, match_score
    if match_score <= params.fault_match_threshold:
        return Verdict.LIKELY_FAULT, 1.0 - match_score
    # Partial corroboration between the thresholds → genuinely ambiguous.
    return Verdict.AMBIGUOUS, params.ambiguous_confidence_cap


def _match_score(usable: list[NeighbourEvidence]) -> float:
    if not usable:
        return 0.0
    total = sum(n.edge_weight for n in usable)
    if total <= 0:
        return 0.0
    return sum(n.edge_weight for n in usable if n.corroborated) / total


def _reason_codes_for(verdict: Verdict) -> list[str]:
    if verdict is Verdict.GENUINE_EVENT:
        return [RC_GENUINE]
    if verdict is Verdict.LIKELY_FAULT:
        return [RC_FAULT]
    return [RC_AMBIGUOUS]


def _notes_for(verdict: Verdict, n_usable: int, params: AdjudicatorParams) -> list[str]:
    notes = ["No headline accuracy figure is reported for this method (standing rule 4)."]
    if verdict is Verdict.AMBIGUOUS and n_usable < params.min_downwind_neighbours:
        notes.append(
            f"Only {n_usable} usable downwind neighbour(s) carried the parameter; "
            f"{params.min_downwind_neighbours} are needed to corroborate a plume."
        )
    return notes


def _build_series(
    event: CandidateEvent, hours: list[pd.Timestamp], usable: list[NeighbourEvidence]
) -> ExpectedActualSeries:
    """An aggregate expected-vs-actual downwind series for the dashboard overlay.

    Anchored on the event hour (excess 0 at t, the plume not yet arrived) and the
    evaluation hour(s); the aggregate is the edge-weighted mean expected and actual
    excess across the usable neighbours.
    """
    timestamps = [pd.Timestamp(event.timestamp).isoformat()] + [t.isoformat() for t in hours]
    if not usable:
        return ExpectedActualSeries(
            timestamps=timestamps,
            expected=[0.0] + [0.0 for _ in hours],
            actual=[0.0] + [None for _ in hours],
        )
    total = sum(n.edge_weight for n in usable) or 1.0
    exp = sum(n.edge_weight * n.expected_excess for n in usable) / total
    act = sum(n.edge_weight * (n.actual_excess or 0.0) for n in usable) / total
    actual: list[float | None] = [0.0, *(act for _ in hours)]
    return ExpectedActualSeries(
        timestamps=timestamps,
        expected=[0.0] + [exp for _ in hours],
        actual=actual,
    )


def _wind_dict(vec: WindVector, wind: WindField) -> dict[str, Any]:
    from provenance.graph.geometry import wind_travel_bearing_deg

    return {
        "from_deg": round(vec.from_deg, 2),
        "to_deg": round(wind_travel_bearing_deg(vec.from_deg), 2),
        "speed": round(vec.speed, 4),
        "speed_unit": vec.speed_unit or wind.speed_unit,
        "provenance": vec.provenance.value,
        "station_count": vec.station_count,
    }


def _ambiguous_without_neighbours(
    event: CandidateEvent,
    vec: WindVector | None,
    wind: WindField,
    covariates: list[CovariateState],
    note: str,
    params: AdjudicatorParams,
    expectation_provenance: str = "analytic",
) -> Adjudication:
    wind_dict = (
        _wind_dict(vec, wind)
        if vec is not None
        else {"provenance": WindProvenance.UNAVAILABLE.value, "speed": 0.0}
    )
    bundle = EvidenceBundle(
        wind=wind_dict,
        downwind_neighbours=[],
        series=ExpectedActualSeries(
            timestamps=[pd.Timestamp(event.timestamp).isoformat()], expected=[0.0], actual=[0.0]
        ),
        match_score=0.0,
        n_downwind=0,
        n_usable=0,
        covariates=covariates,
        reason_codes=[RC_AMBIGUOUS],
        notes=[note, "No headline accuracy figure is reported for this method."],
        expectation_provenance=expectation_provenance,
    )
    confidence = params.ambiguous_confidence_cap
    return Adjudication(
        event=event,
        verdict=Verdict.AMBIGUOUS,
        confidence=round(confidence, 4),
        confidence_band=params.band(confidence),
        routes_to_review=True,
        evidence=bundle,
    )
