# AGENTS.md

This file is a pointer, not a rulebook. **Read [CLAUDE.md](CLAUDE.md) first, in
full, before touching this repository.**

Provenance is an AI trust and quality-assurance layer for Debrecen's Green
Sentinel environmental sensor network, built for the DEIK.AI Challenge 2026. It
scores every reading for genuineness rather than just presence.

CLAUDE.md is the single authoritative rulebook for working in this repo: the ten
standing rules, the build order, the branch/PR/tag workflow, and the "never do
this" list all live there. Any agent, Claude Code or otherwise, must follow it.

The two commands that matter most while you work: branch per change off an
up-to-date `main`, and run `make check` (lint + mypy strict + pytest with the
coverage gate) before opening a PR.

The standing rules are deliberately **not duplicated here**. One copy, one
source of truth — so this file and CLAUDE.md cannot drift apart and contradict
each other. `tests/architecture/test_agents_md.py` enforces that this file stays
a pointer.
