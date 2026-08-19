"""The propagation adjudicator: three verdicts, and the invariants around AMBIGUOUS."""

from __future__ import annotations

import pandas as pd
import pytest

from provenance.config.loading import load_graph_config
from provenance.graph import scenarios as S
from provenance.graph.adjudicate import (
    Adjudication,
    CandidateEvent,
    ConfidenceBand,
    EvidenceBundle,
    Verdict,
    validate_event,
)


@pytest.fixture
def cfg() -> dict:
    return load_graph_config()


def _adjudicate(scenario: S.Scenario, cfg: dict) -> Adjudication:
    return validate_event(scenario.event, scenario.points, scenario.wind, scenario.frame, cfg)


def test_corroborated_plume_is_genuine(cfg: dict) -> None:
    adj = _adjudicate(S.corroborated_plume(), cfg)
    assert adj.verdict is Verdict.GENUINE_EVENT
    assert adj.routes_to_review is False
    assert adj.evidence.match_score >= cfg["adjudicator"]["genuine_match_threshold"]
    assert adj.evidence.reason_codes == ["R22"]


def test_isolated_spike_is_likely_fault(cfg: dict) -> None:
    adj = _adjudicate(S.isolated_fault(), cfg)
    assert adj.verdict is Verdict.LIKELY_FAULT
    assert adj.routes_to_review is False
    assert adj.evidence.match_score <= cfg["adjudicator"]["fault_match_threshold"]
    # The fault verdict surfaces R17 — "contradicts N connected neighbours".
    assert adj.evidence.reason_codes == ["R17"]


def test_partial_corroboration_is_ambiguous_never_forced_binary(cfg: dict) -> None:
    adj = _adjudicate(S.partial_ambiguous(), cfg)
    assert adj.verdict is Verdict.AMBIGUOUS
    assert adj.routes_to_review is True
    assert adj.evidence.reason_codes == ["R23"]
    # Genuinely between the thresholds — not snapped to genuine or fault.
    lo = cfg["adjudicator"]["fault_match_threshold"]
    hi = cfg["adjudicator"]["genuine_match_threshold"]
    assert lo < adj.evidence.match_score < hi


def test_ambiguous_is_never_high_confidence(cfg: dict) -> None:
    adj = _adjudicate(S.partial_ambiguous(), cfg)
    assert adj.confidence_band is not ConfidenceBand.HIGH
    assert adj.confidence <= cfg["adjudicator"]["ambiguous_confidence_cap"]


def test_ambiguous_value_object_rejects_high_confidence() -> None:
    # The invariant lives in the value object, not a serialiser: an AMBIGUOUS verdict
    # cannot be constructed as high confidence at all.
    event = CandidateEvent("X", "PM10", pd.Timestamp("2026-06-01T00:00:00"), 100.0, 30.0)
    empty = EvidenceBundle(
        wind={},
        downwind_neighbours=[],
        series=_stub_series(),
        match_score=0.4,
        n_downwind=0,
        n_usable=0,
        covariates=[],
        reason_codes=["R23"],
    )
    with pytest.raises(ValueError, match="high confidence"):
        Adjudication(
            event=event,
            verdict=Verdict.AMBIGUOUS,
            confidence=0.9,
            confidence_band=ConfidenceBand.HIGH,
            routes_to_review=True,
            evidence=empty,
        )


def test_ambiguous_must_route_to_review() -> None:
    event = CandidateEvent("X", "PM10", pd.Timestamp("2026-06-01T00:00:00"), 100.0, 30.0)
    with pytest.raises(ValueError, match="route to human review"):
        Adjudication(
            event=event,
            verdict=Verdict.AMBIGUOUS,
            confidence=0.4,
            confidence_band=ConfidenceBand.LOW,
            routes_to_review=False,
            evidence=EvidenceBundle(
                wind={},
                downwind_neighbours=[],
                series=_stub_series(),
                match_score=0.4,
                n_downwind=0,
                n_usable=0,
                covariates=[],
                reason_codes=["R23"],
            ),
        )


def test_only_ambiguous_routes_to_review() -> None:
    event = CandidateEvent("X", "PM10", pd.Timestamp("2026-06-01T00:00:00"), 100.0, 30.0)
    with pytest.raises(ValueError, match="only an AMBIGUOUS"):
        Adjudication(
            event=event,
            verdict=Verdict.GENUINE_EVENT,
            confidence=0.8,
            confidence_band=ConfidenceBand.HIGH,
            routes_to_review=True,
            evidence=EvidenceBundle(
                wind={},
                downwind_neighbours=[],
                series=_stub_series(),
                match_score=0.8,
                n_downwind=2,
                n_usable=2,
                covariates=[],
                reason_codes=["R22"],
            ),
        )


def test_no_wind_routes_to_review(cfg: dict) -> None:
    # A plume cannot be assessed without wind; the honest answer is "review", not a guess.
    scenario = S.corroborated_plume()
    windless = scenario.frame[~scenario.frame["parameter"].isin(["Wind_Direction", "Wind_Speed"])]
    from provenance.graph.wind import WindField

    adj = validate_event(
        scenario.event, scenario.points, WindField.from_frame(windless), windless, cfg
    )
    assert adj.verdict is Verdict.AMBIGUOUS
    assert adj.routes_to_review is True
    assert adj.evidence.n_downwind == 0


def test_evidence_bundle_is_complete(cfg: dict) -> None:
    adj = _adjudicate(S.corroborated_plume(), cfg)
    d = adj.to_dict()
    ev = d["evidence"]
    assert set(ev) >= {
        "wind",
        "downwind_neighbours",
        "series",
        "match_score",
        "n_downwind",
        "n_usable",
        "covariates",
        "reason_codes",
        "notes",
    }
    # Wind vector, downwind neighbours with weights, expected vs actual, covariate state.
    assert ev["wind"]["provenance"] == "station-local"
    assert len(ev["downwind_neighbours"]) >= 2
    assert {c["name"] for c in ev["covariates"]} == {"traffic", "weather"}
    assert ev["series"]["expected"] and ev["series"]["actual"]


def test_no_headline_accuracy_figure_is_reported(cfg: dict) -> None:
    # Standing rule 4 / §16 critique 2: per-case evidence only, never a method accuracy.
    adj = _adjudicate(S.corroborated_plume(), cfg)
    joined = " ".join(adj.evidence.notes).lower()
    assert "no headline accuracy" in joined
    assert "accuracy" not in {k.lower() for k in adj.to_dict()["evidence"]}


def _stub_series():
    from provenance.graph.adjudicate import ExpectedActualSeries

    return ExpectedActualSeries(timestamps=["2026-06-01T00:00:00"], expected=[0.0], actual=[0.0])
