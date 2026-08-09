"""The sign-off gate as a static call-graph invariant (§2, standing rule 5).

*No code path may publish a public-facing alert without a human sign-off record.*
This test proves it without running anything: it walks the AST of the whole shipped
package and asserts

1. the channel senders (``send_webhook``/``send_email``/``send_sms``) are *called*
   only inside ``api/decision/channels.py``;
2. the router-facing primitive ``deliver`` is *called* only inside
   ``api/decision/gate.py`` — so every path to a send goes through the gate;
3. the gate function that calls ``deliver`` also calls ``validate_signoff`` — so the
   gate cannot deliver without checking a sign-off first.

If a future change routes a dispatch around the gate, or drops the sign-off check,
one of these assertions fails. That is the ethical commitment made mechanical, per
the phase-7 prompt (\"a static call-graph assertion, not a runtime check alone\").
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.demo_critical]

SRC = Path(__file__).resolve().parents[2] / "src" / "provenance"

SENDERS = {"send_webhook", "send_email", "send_sms"}
DELIVER = "deliver"
VALIDATOR = "validate_signoff"

CHANNELS_MODULE = SRC / "api" / "decision" / "channels.py"
GATE_MODULE = SRC / "api" / "decision" / "gate.py"


def _called_names(func: ast.AST) -> set[str]:
    """Every name that appears as a *call target* inside a function body."""
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _functions(path: Path) -> dict[str, set[str]]:
    """Map each function in a module to the set of names it calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            out[node.name] = _called_names(node)
    return out


def _all_source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_channel_senders_are_called_only_inside_channels_module() -> None:
    offenders: list[str] = []
    for path in _all_source_files():
        if path == CHANNELS_MODULE:
            continue
        for name, called in _functions(path).items():
            hit = called & SENDERS
            if hit:
                offenders.append(f"{path.relative_to(SRC)}::{name} calls {sorted(hit)}")
    assert not offenders, (
        "A channel sender is reachable outside api/decision/channels.py, which is a path "
        "to a public alert that skips the sign-off gate:\n  " + "\n  ".join(offenders)
    )


def test_deliver_is_called_only_inside_the_gate() -> None:
    offenders: list[str] = []
    for path in _all_source_files():
        if path in {GATE_MODULE, CHANNELS_MODULE}:
            continue
        for name, called in _functions(path).items():
            if DELIVER in called:
                offenders.append(f"{path.relative_to(SRC)}::{name}")
    assert not offenders, (
        "channels.deliver is called outside the gate; every dispatch must go through "
        "gate.dispatch:\n  " + "\n  ".join(offenders)
    )


def test_the_gate_validates_a_signoff_before_it_delivers() -> None:
    funcs = _functions(GATE_MODULE)
    delivering = {name for name, called in funcs.items() if DELIVER in called}
    assert delivering, "Expected gate.py to contain the single function that calls deliver()."
    for name in delivering:
        assert VALIDATOR in funcs[name], (
            f"gate.py::{name} calls deliver() without calling {VALIDATOR}() — the gate "
            "must check a sign-off before every send (standing rule 5)."
        )
