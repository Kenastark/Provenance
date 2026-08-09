"""Freeze the demo centrepiece so no change can silently move its verdict.

The real ~4,100 µg/m³ KER11 event lives in the un-committed Green Sentinel export
(standing rule 7), so CI freezes a KER11-shaped corroborated plume built by
``scenarios.corroborated_plume()`` instead. The fixture was generated FROM the run;
if the geometry, the edge weight, the propagation maths, or the thresholds change in
a way that moves the verdict, the match score, or the neighbour set, this fails loudly
rather than the demo quietly adjudicating something else on stage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from provenance.config.loading import load_graph_config
from provenance.graph import scenarios as S
from provenance.graph.adjudicate import validate_event

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "graph" / "centrepiece_adjudication.json"
)


@pytest.mark.demo_critical
def test_centrepiece_adjudication_is_frozen() -> None:
    frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenario = S.corroborated_plume()
    adj = validate_event(
        scenario.event, scenario.points, scenario.wind, scenario.frame, load_graph_config()
    )

    assert adj.verdict.value == frozen["verdict"]
    assert adj.confidence == pytest.approx(frozen["confidence"])
    assert adj.confidence_band.value == frozen["confidence_band"]
    assert adj.routes_to_review == frozen["routes_to_review"]
    assert adj.evidence.match_score == pytest.approx(frozen["match_score"])
    assert adj.evidence.n_usable == frozen["n_usable"]
    assert adj.evidence.reason_codes == frozen["reason_codes"]

    got = {
        n.station_id: (round(n.edge_weight, 6), round(n.expected_excess, 4), n.corroborated)
        for n in adj.evidence.downwind_neighbours
    }
    want = {
        n["station_id"]: (n["edge_weight"], n["expected_excess"], n["corroborated"])
        for n in frozen["neighbours"]
    }
    assert got == want


@pytest.mark.demo_critical
def test_centrepiece_is_genuine_and_not_routed() -> None:
    # The one-line demo assertion: the corroborated plume is a real event, not a fault,
    # and does not need a human — while the ambiguous contrast case does.
    scenario = S.corroborated_plume()
    adj = validate_event(
        scenario.event, scenario.points, scenario.wind, scenario.frame, load_graph_config()
    )
    assert adj.verdict.value == "GENUINE_EVENT"
    assert adj.routes_to_review is False
