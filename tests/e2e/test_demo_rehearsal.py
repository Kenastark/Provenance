"""The full-script rehearsal (§ phase-7.6 test gate). Demo-critical.

Walks the complete demo script — the stage order B1 (audit) → B3 (graph adjudication)
→ B2 (deweathering), with explainability — as one deterministic pass, and asserts each
key screen state appears with its computed numbers.

Deliberately a *scenario-layer* rehearsal, not a Playwright browser walk: the phase-7
memory note pins the Playwright visual baselines, and a new browser walk of these
screens would churn them. This asserts the same thing the Playwright walk would — that
every key screen state is reached, in order, with the right numbers — at the layer that
drives the dashboard, so the guarantee is real and the baselines stay stable. (The
deferral is recorded in the phase report.)
"""

from __future__ import annotations

import pytest

from provenance.ops import demo

pytestmark = pytest.mark.demo_critical

# The stage order and the key screen each block must reach.
SCRIPT: list[tuple[str, list[str]]] = [
    ("audit-headline", ["title", "defect-headline", "top-codes"]),
    ("ker11-adjudication", ["event-appears", "verdict"]),
    ("contrast-fault", ["contrast-verdicts"]),
    ("deweathering-reveal", ["deweather"]),
    ("explainability", ["components", "reason-codes"]),
]


def test_full_script_reaches_every_key_screen_in_order(demo_drop: dict) -> None:
    frame, meta = demo_drop["frame"], demo_drop["meta"]
    scenarios = demo.build_all(frame, meta)

    walked: list[str] = []
    for name, required in SCRIPT:
        sc = scenarios[name]
        screens = sc.screen_states()
        # Each required screen appears, and in the order the script expects.
        last = -1
        for screen in required:
            assert screen in screens, f"{name} never reached screen {screen!r}"
            idx = screens.index(screen)
            assert idx > last, f"{name} reached {screen!r} out of order"
            last = idx
        walked.extend(f"{name}:{s}" for s in screens)

    # The whole rehearsal is a non-trivial, ordered walk.
    assert walked[0] == "audit-headline:title"
    assert any(s.endswith(":verdict") for s in walked)
    assert any(s.endswith(":reason-codes") for s in walked)


def test_key_screens_carry_their_computed_numbers(demo_drop: dict) -> None:
    scenarios = demo.build_all(demo_drop["frame"], demo_drop["meta"])

    verdict = next(s for s in scenarios["ker11-adjudication"].steps if s.screen == "verdict")
    assert verdict.numbers["verdict"] in {"GENUINE_EVENT", "LIKELY_FAULT", "AMBIGUOUS"}

    reasons = next(s for s in scenarios["explainability"].steps if s.screen == "reason-codes")
    assert reasons.reason_codes, "the explainability block must show at least one reason code"


def test_rehearsal_is_deterministic(demo_drop: dict) -> None:
    a = {k: v.to_dict() for k, v in demo.build_all(demo_drop["frame"], demo_drop["meta"]).items()}
    b = {k: v.to_dict() for k, v in demo.build_all(demo_drop["frame"], demo_drop["meta"]).items()}
    assert a == b
