"""Demo mode: deterministic replay of fixed scenarios (§ phase-7.6). Demo-critical."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from provenance.cli.main import app
from provenance.ops import demo

pytestmark = [pytest.mark.integration, pytest.mark.demo_critical]

runner = CliRunner()


def test_every_scenario_builds_deterministically(demo_drop: dict) -> None:
    frame, meta = demo_drop["frame"], demo_drop["meta"]
    for name in demo.available_scenarios():
        a = demo.build_scenario(name, frame, meta)
        b = demo.build_scenario(name, frame, meta)
        assert a.to_dict() == b.to_dict(), f"{name} is not deterministic"
        assert a.steps, f"{name} produced no steps"


def test_speed_scales_offsets_but_not_content(demo_drop: dict) -> None:
    frame, meta = demo_drop["frame"], demo_drop["meta"]
    slow = demo.build_scenario("audit-headline", frame, meta, speed=1.0)
    fast = demo.build_scenario("audit-headline", frame, meta, speed=2.0)
    # Same screens and numbers, tighter timing.
    assert [s.numbers for s in slow.steps] == [s.numbers for s in fast.steps]
    assert fast.steps[-1].at_offset_ms < slow.steps[-1].at_offset_ms


def test_audit_headline_numbers_are_computed_from_the_corpus(demo_drop: dict) -> None:
    sc = demo.build_scenario("audit-headline", demo_drop["frame"], demo_drop["meta"])
    headline = next(s for s in sc.steps if s.screen == "defect-headline")
    assert headline.numbers["defect_rate_pct"] >= 0.0
    assert headline.numbers["n_defective_cells"] >= 1  # the fixture injects faults


def test_cli_demo_run_is_byte_for_byte_reproducible(demo_drop: dict, tmp_path) -> None:
    drop = str(demo_drop["path"])
    out1, out2 = tmp_path / "a.json", tmp_path / "b.json"
    for out in (out1, out2):
        result = runner.invoke(
            app,
            ["demo", "run", "--scenario", "ker11-adjudication", "--data", drop, "--out", str(out)],
        )
        assert result.exit_code == 0, result.output
    assert out1.read_text() == out2.read_text()
    payload = json.loads(out1.read_text())
    assert payload["name"] == "ker11-adjudication"
    assert payload["steps"]


def test_contrast_scenario_shows_two_distinct_events(demo_drop: dict) -> None:
    # The contrast must never be the same event shown twice. On a wind-less corpus no
    # verdict contrast exists, so it falls back to a different station and says so
    # honestly (verdicts_differ=False) rather than implying a contrast that isn't there.
    sc = demo.build_scenario("contrast-fault", demo_drop["frame"], demo_drop["meta"])
    step = next(s for s in sc.steps if s.screen == "contrast-verdicts")
    a, b = step.numbers["a"], step.numbers["b"]
    assert b is not None
    assert (a["station_id"], a["timestamp_utc"]) != (b["station_id"], b["timestamp_utc"])
    assert "verdicts_differ" in step.numbers
    # The step headline must not claim differing verdicts when there are none.
    if not step.numbers["verdicts_differ"]:
        assert a["verdict"] == b["verdict"]
        assert "Different verdicts" not in step.headline


def test_cli_demo_run_rejects_an_unknown_scenario(demo_drop: dict) -> None:
    result = runner.invoke(
        app, ["demo", "run", "--scenario", "nope", "--data", str(demo_drop["path"])]
    )
    assert result.exit_code == 1


def test_cli_demo_run_fails_loudly_without_a_corpus(tmp_path) -> None:
    result = runner.invoke(
        app, ["demo", "run", "--scenario", "audit-headline", "--data", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "No demo corpus" in result.output
