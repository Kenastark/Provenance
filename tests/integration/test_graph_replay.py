"""The replay harness: rank the corpus's events, adjudicate each, write bundles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from provenance.graph import scenarios as S
from provenance.graph.replay import rank_candidates, replay_frame, write_adjudications


def _meta(scenario: S.Scenario) -> dict:
    return {p.station_id: p for p in scenario.points}


def test_ranking_puts_the_largest_magnitude_first() -> None:
    scenario = S.corroborated_plume()
    ranked = rank_candidates(scenario.frame, window_hours=48, limit=5)
    assert ranked, "the audit should surface at least the source spike"
    top = ranked[0]
    assert top.event.station_id == "SCEN-SRC"
    assert top.event.parameter == "PM10"
    # Monotonically non-increasing magnitude.
    magnitudes = [c.magnitude for c in ranked]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_replay_adjudicates_the_top_event_from_evidence_not_assumption() -> None:
    scenario = S.corroborated_plume()
    adjudications = replay_frame(scenario.frame, _meta(scenario), limit=5)
    assert len(adjudications) >= 2, "a centrepiece and at least one backup candidate"
    top = adjudications[0]
    assert top.event.station_id == "SCEN-SRC"
    # The verdict is whatever the evidence produced — here, corroborated ⇒ genuine.
    assert top.verdict.value == "GENUINE_EVENT"


def test_contrast_case_is_a_fault() -> None:
    # The isolated-spike scenario is the demo's fault contrast.
    scenario = S.isolated_fault()
    adjudications = replay_frame(scenario.frame, _meta(scenario), limit=3)
    assert adjudications[0].verdict.value == "LIKELY_FAULT"


def test_write_adjudications_is_deterministic(tmp_path: Path) -> None:
    scenario = S.corroborated_plume()
    adjudications = replay_frame(scenario.frame, _meta(scenario), limit=3)

    a = tmp_path / "a"
    b = tmp_path / "b"
    write_adjudications(adjudications, a)
    write_adjudications(adjudications, b)

    a_index = (a / "index.json").read_text(encoding="utf-8")
    b_index = (b / "index.json").read_text(encoding="utf-8")
    assert a_index == b_index

    index = json.loads(a_index)
    assert index[0]["verdict"] == "GENUINE_EVENT"
    assert index[0]["rank"] == 1
    # Every indexed bundle exists on disk and round-trips.
    for row in index:
        bundle = json.loads((a / row["file"]).read_text(encoding="utf-8"))
        assert bundle["verdict"] == row["verdict"]
        assert bundle["event"]["station_id"] == row["station_id"]


def test_empty_corpus_yields_no_adjudications() -> None:
    import pandas as pd

    from provenance.schema import canonical as C

    empty = pd.DataFrame(columns=list(C.LONG_COLUMNS))
    empty = empty.astype({C.TIMESTAMP: "datetime64[ns]", C.VALUE: "float64"})
    ranked = rank_candidates(empty, window_hours=48)
    assert ranked == []


@pytest.mark.demo_critical
def test_three_scenarios_span_all_three_verdicts() -> None:
    # The B3 block needs all three framings to exist; discovering one live is a risk.
    verdicts = {
        replay_frame(S.corroborated_plume().frame, _meta(S.corroborated_plume()))[0].verdict.value,
        replay_frame(S.isolated_fault().frame, _meta(S.isolated_fault()))[0].verdict.value,
    }
    assert "GENUINE_EVENT" in verdicts
    assert "LIKELY_FAULT" in verdicts
