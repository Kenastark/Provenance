"""AGENTS.md must stay a pointer to CLAUDE.md, not a second copy of it.

CLAUDE.md is the single authoritative rulebook. AGENTS.md exists only so that
agents which look for that filename by convention land somewhere useful. If
someone "helpfully" pastes CLAUDE.md's content in here, the two files can drift
apart and start contradicting each other - which is worse than AGENTS.md not
existing at all. These checks are a structural guard against that, not a style
preference.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO / "AGENTS.md"

MAX_LINES = 40

# Matches a markdown ordered-list item: "1. ", "2. ", ... at the start of a line
# (optionally indented), which is how CLAUDE.md's standing rules and "never do
# this" list are formatted.
NUMBERED_LIST_ITEM = re.compile(r"^\s*\d+\.\s+\S")


def test_agents_md_exists() -> None:
    assert AGENTS_MD.exists(), "AGENTS.md is missing from the repository root."


def test_agents_md_stays_short() -> None:
    lines = AGENTS_MD.read_text("utf-8").splitlines()
    assert len(lines) <= MAX_LINES, (
        f"AGENTS.md has grown to {len(lines)} lines (limit {MAX_LINES}). It is meant "
        "to be a short pointer to CLAUDE.md, not a growing document in its own "
        "right - trim it back rather than raising the limit."
    )


def test_agents_md_does_not_contain_a_numbered_rules_list() -> None:
    lines = AGENTS_MD.read_text("utf-8").splitlines()
    numbered = [line for line in lines if NUMBERED_LIST_ITEM.match(line)]
    assert not numbered, (
        "AGENTS.md contains a numbered list, which is how CLAUDE.md's standing "
        "rules and 'never do this' list are formatted. AGENTS.md must not "
        "duplicate CLAUDE.md's rules - point at CLAUDE.md instead of copying "
        f"from it. Offending line(s): {numbered!r}"
    )


def test_agents_md_points_at_claude_md() -> None:
    text = AGENTS_MD.read_text("utf-8")
    assert "CLAUDE.md" in text, (
        "AGENTS.md no longer references CLAUDE.md. It exists specifically to "
        "point agents at the authoritative rulebook."
    )
