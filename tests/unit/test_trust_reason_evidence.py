"""Every trust reason code must arrive with the numbers its sentence needs.

Standing rule 9 says a trust score never renders without a reason code. A reason
code whose sentence cannot be filled is only half of that: the dashboard was
rendering "Trust is reduced by disagreement with — neighbouring station(s)" because
the engine computed the count, wrote it into a prose ``detail`` string, and threw
the number itself away.

These tests pin the contract: for each trust code the engine can emit, the evidence
travelling with the score contains every placeholder that code's registry sentence
asks for, so the sentence renders as a sentence.
"""

from __future__ import annotations

import re

import pytest

from provenance.config.loading import load_thresholds
from provenance.config.reason_codes import REASON_CODES
from provenance.detectors import registry
from provenance.detectors.base import AuditContext
from provenance.grid.coverage import build_coverage
from provenance.trust.engine import compute_trust, latest_timestamp
from provenance.trust.score import TrustScore


@pytest.fixture(scope="module")
def scored() -> dict[str, TrustScore]:
    """Every fixture station scored once, from the seeded synthetic corpus."""
    from provenance.fixtures.generator import generate

    frame, _ = generate()
    coverage = build_coverage(frame)
    defects = registry.run_detectors(
        frame, AuditContext(thresholds=load_thresholds(), coverage=coverage)
    )
    at = latest_timestamp(frame)
    stations = sorted(frame["station_id"].unique())
    return {
        station: compute_trust(frame, defects, station, at, coverage=coverage)
        for station in stations
    }


def placeholders(code: str) -> set[str]:
    """The placeholder names a code's operator sentence asks to be filled."""
    return set(re.findall(r"\{(\w+)\}", REASON_CODES[code].sentence))


def test_every_trust_code_declares_which_placeholders_it_needs() -> None:
    """Guards the test below: if a sentence gains a placeholder, this list moves."""
    assert placeholders("T00") == set()
    assert placeholders("T01") == {"n_defects"}
    assert placeholders("T02") == {"pct"}
    assert placeholders("T03") == {"n"}
    assert placeholders("T04") == set()
    assert placeholders("T05") == {"min_peers"}


@pytest.mark.parametrize("station", ["STA-01", "STA-02", "STA-03", "STA-04"])
def test_score_evidence_fills_every_reason_code_sentence(
    scored: dict[str, TrustScore], station: str
) -> None:
    """No trust code on any fixture station renders with an unfilled placeholder."""
    score = scored[station]
    evidence = score.evidence

    unfillable: list[str] = []
    for code in score.reason_codes:
        missing = placeholders(code) - set(evidence)
        if missing:
            unfillable.append(f"{code} needs {sorted(missing)}")

    assert not unfillable, (
        f"{station}: these codes cannot render as sentences: {unfillable}. "
        f"Evidence carried: {sorted(evidence)}"
    )


@pytest.mark.parametrize("station", ["STA-01", "STA-02", "STA-03", "STA-04"])
def test_rendered_sentences_contain_no_braces(scored: dict[str, TrustScore], station: str) -> None:
    """The rendered sentence is what an operator reads. It must be a sentence."""
    score = scored[station]
    for code in score.reason_codes:
        rendered = REASON_CODES[code].render(**score.evidence)
        assert "{" not in rendered and "}" not in rendered, (
            f"{station}/{code} rendered with a raw placeholder: {rendered!r}"
        )


def test_evidence_survives_the_component_round_trip(scored: dict[str, TrustScore]) -> None:
    """Evidence rides on the components, which is what the JSON column persists.

    ``components`` is already a JSON column of arbitrary dicts, so carrying the
    evidence there is what makes this reach the API without a schema migration.
    """
    score = scored["STA-01"]
    from_components: dict[str, object] = {}
    for component in score.components:
        from_components.update(component.to_dict()["evidence"])

    assert from_components == score.evidence
    assert from_components, "the fixture station should produce at least one figure"


def test_health_evidence_matches_the_active_defect_count(scored: dict[str, TrustScore]) -> None:
    """T01's number is the count, not an approximation of it."""
    score = scored["STA-01"]
    health = next(c for c in score.components if c.name == "HealthConf")

    assert "n_defects" in health.evidence
    # `detail` is the prose the UI used to have to fall back on; the number in the
    # evidence must be the same number, or the two halves of the screen disagree.
    assert str(health.evidence["n_defects"]) in health.detail


@pytest.mark.parametrize("station", ["STA-01", "STA-02", "STA-03", "STA-04"])
def test_component_evidence_keys_are_pairwise_disjoint(
    scored: dict[str, TrustScore], station: str
) -> None:
    """No two components may own the same evidence key.

    ``TrustScore.evidence`` merges the four components' dicts. If two ever emitted
    the same key, one would silently overwrite the other and a reason-code sentence
    would render the wrong component's figure. The merge deliberately carries no
    runtime guard (it is on the per-instant scoring path), so this is where a future
    collision is caught - across four stations whose conditions differ enough to
    exercise every component's populated branch.
    """
    seen: dict[str, str] = {}
    collisions: list[str] = []
    for component in scored[station].components:
        for key in component.evidence:
            if key in seen:
                collisions.append(f"{key!r} claimed by both {seen[key]} and {component.name}")
            else:
                seen[key] = component.name

    assert not collisions, (
        f"{station}: components share evidence keys, so a merged figure is ambiguous: "
        f"{collisions}. Rename one of the colliding keys, or the sentence will show "
        "the wrong number."
    )


def test_all_four_components_contribute_at_least_one_figure(scored: dict[str, TrustScore]) -> None:
    """Guards the disjointness test: it is only meaningful if every component speaks.

    A disjointness check passes vacuously if a component contributes no keys, so this
    asserts the four §7.8 components each carry evidence on at least one fixture
    station - i.e. the parametrised test above is actually exercising all of them.
    """
    contributing: set[str] = set()
    for score in scored.values():
        for component in score.components:
            if component.evidence:
                contributing.add(component.name)

    assert contributing == {
        "HealthConf",
        "ImputationCertainty",
        "CrossSensorConsistency",
        "PhysicalPlausibility",
    }, f"Only these components carried evidence anywhere: {sorted(contributing)}"
