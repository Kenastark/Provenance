# Phase reports

One file per phase, written by Claude Code itself at the end of each session:
`phase-0-report.md`, `phase-1-report.md`, and so on.

These are progress records, not ADRs - they don't get superseded or revised, they
just accumulate. Each one covers: what was built, what the test gate showed, any
deviations from the phase prompt, and anything flagged for review before the next
phase builds on top of it.

If a report's "flag for review" section is empty or says "nothing" for every
phase in a row, that's worth being suspicious of - it usually means the report
stopped being written honestly rather than that seven phases in a row went
perfectly.
