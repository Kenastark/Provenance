# Update 0 — AGENTS.md

Branch: `update-0-agents-md`. Tag: `v1.0.1-update`.

## What was built

Added a tracked `AGENTS.md` at the repository root: a ~20-line pointer that
states what Provenance is in two sentences, says CLAUDE.md is the authoritative
rulebook that must be read first, names the gate (`make check`) and the
branch-per-change workflow, and explicitly says the ten standing rules live only
in CLAUDE.md, on purpose, so the two files can't contradict each other. Added
`tests/architecture/test_agents_md.py`, which fails if AGENTS.md exceeds 40
lines, loses its reference to CLAUDE.md, or gains a numbered list (the format
CLAUDE.md's standing rules and "never do this" list use) — a structural guard
against someone later pasting CLAUDE.md's content into it. Added a one-line note
to CLAUDE.md's own header pointing at AGENTS.md, and a CHANGELOG entry.

## Test gate

`make check` (ruff, ruff format, mypy strict, pytest with the 88% coverage
floor, frontend-contract drift check): green. 640 tests passed (4 new, in
`test_agents_md.py`), 90.49% coverage. No frontend change, so `make web-lint`
and `make web-test` were not run and no Playwright baselines moved.

## Deviations from the prompt

- **AGENTS.md is 21 lines, not "about 15."** Fitting all four required elements
  (a–d) in without cramming them into unreadable single lines pushed it slightly
  over; it's still well under the 40-line test ceiling.
- Found an **untracked** `AGENTS.md` already sitting at the repo root before this
  branch was created — content-identical to CLAUDE.md (with a couple of
  `Codex`/`.Codex` references swapped in place of `Claude Code`/`.claude`),
  i.e. already the exact anti-pattern this update guards against. It was never
  committed, so nothing in git history changes; I overwrote it with the pointer
  version rather than layering on top of it. Flagging this in case it came from
  another tool run against this repo that you'd want to know about.
- Added a CHANGELOG.md `[Unreleased] / Added` entry, per the working agreements
  ("Every PR: ... CHANGELOG.md entry"), even though the update prompt didn't
  mention it explicitly.

## Flag for review

The pre-existing untracked `AGENTS.md` (see above) — worth confirming where it
came from, since it wasn't something this session wrote and it wasn't tracked by
git either.
