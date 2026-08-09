"""The Alert Centre ranks by RISK, not by certainty (§9.5, phase 7).

The load-bearing property, asserted with a constructed pair: a high-confidence,
high-exposure **genuine event** must outrank a high-confidence, low-exposure **sensor
fault**. A fault is a maintenance problem, not a public hazard, so however sure the
adjudicator is that it is a fault, it must not lead the Alert Centre over a real event
that exposes more people.
"""

from __future__ import annotations

import pytest

from provenance.ops.alerts import AlertCandidate, alert_risk, rank_alerts

pytestmark = pytest.mark.unit


def _candidate(
    event_id: int,
    *,
    verdict: str,
    exposure: float,
    confidence: float,
    severity: str = "critical",
) -> AlertCandidate:
    return AlertCandidate(
        event_id=event_id,
        station_id=f"STA-{event_id:02d}",
        parameter="PM10",
        severity=severity,
        verdict=verdict,
        confidence=confidence,
        exposure=exposure,
        headline="constructed",
        timestamp_utc="2026-06-02T20:00:00",
    )


def test_genuine_high_exposure_event_outranks_confident_low_exposure_fault() -> None:
    genuine = _candidate(1, verdict="GENUINE_EVENT", exposure=1.6, confidence=0.9)
    fault = _candidate(2, verdict="LIKELY_FAULT", exposure=0.6, confidence=0.9)

    ranked = rank_alerts([fault, genuine])

    assert ranked[0].candidate.event_id == genuine.event_id
    assert ranked[1].candidate.event_id == fault.event_id
    assert ranked[0].risk > ranked[1].risk


def test_genuineness_dominates_even_when_the_fault_has_higher_exposure() -> None:
    # A real event at a quiet site still outranks a confident fault at a busy one:
    # the fault's public-health risk is near zero because the number is not real.
    genuine_quiet = _candidate(1, verdict="GENUINE_EVENT", exposure=0.6, confidence=0.9)
    fault_busy = _candidate(2, verdict="LIKELY_FAULT", exposure=1.6, confidence=0.95)

    ranked = rank_alerts([fault_busy, genuine_quiet])

    assert ranked[0].candidate.event_id == genuine_quiet.event_id


def test_ranked_alert_carries_its_risk_factors_never_a_bare_number() -> None:
    scored = alert_risk(_candidate(1, verdict="GENUINE_EVENT", exposure=1.2, confidence=0.8))
    payload = scored.to_dict()
    assert set(payload["risk_factors"]) == {
        "genuineness",
        "exposure",
        "hazard",
        "confidence_weight",
    }
    assert payload["risk"] > 0


def test_ranking_is_deterministic() -> None:
    candidates = [
        _candidate(3, verdict="GENUINE_EVENT", exposure=1.0, confidence=0.7),
        _candidate(1, verdict="AMBIGUOUS", exposure=1.4, confidence=0.5),
        _candidate(2, verdict="LIKELY_FAULT", exposure=1.6, confidence=0.9),
    ]
    order_a = [a.candidate.event_id for a in rank_alerts(candidates)]
    order_b = [a.candidate.event_id for a in rank_alerts(list(reversed(candidates)))]
    assert order_a == order_b
