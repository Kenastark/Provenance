# Update 9 — the KER11 verdict and demo narration

Branch: `update-9-ker11-verdict`. Tag: `v1.0.10-update`.

## What was built

`docs/adjudications/ker11-4100-evidence-v1.1.md` — the verdict and demo
narration that `ker11-4100-evidence-v1.0.md` (Update 8) deliberately withheld.

Sequence: Claude Code assembled the evidence in v1.0 and reported it with no
verdict, as instructed. Asked for a plain-language explanation and a
recommendation on each of v1.0's seven open questions, Claude Code proposed:
keep the `LIKELY_FAULT` call, but frame it as "a real local trigger producing
an invalid reading" rather than "random malfunction" or "genuine citywide
event" - because the value exceeds the sensor's own physical ceiling
regardless of anything else, no neighbouring station shows any response, and
the hour-long build-up/decay plus a delayed PM2.5 echo argue against a
context-free, instantaneous glitch. Ikenna Udeani reviewed and adopted that
recommendation on 2026-08-21. v1.1 records the decision, resolves each of the
seven open questions individually, and drafts suggested stage narration that
avoids citing the adjudicator's confidence number or any headline accuracy
figure (standing rule 4).

No source file changed. v1.0's evidence, commands, and numbers are untouched;
this is additive per standing rule 10 (documents are versioned, never edited
in place).

## Test gate

`make check` - unaffected by a docs-only change; run for the standing gate
discipline regardless. Result below.

```
$ ruff check src tests            # clean, no output
$ ruff format --check src tests   # clean, no output
$ mypy                             # clean, no output
$ pytest
[... per-file coverage table elided (176 files) ...]
------------------------------------------------------------------------------------------
TOTAL                                           7460    524   1410    211    91%
Required test coverage of 88% reached. Total coverage: 90.65%
========== 673 passed, 2 deselected, 62 warnings in 332.82s (0:05:32) ==========
$ python scripts/gen_frontend_contract.py --check
Frontend contract is current.
$ cd apps/web && pnpm gen:types && git diff --exit-code -- src/api/schema.d.ts
> @provenance/web@0.0.1 gen:types
> openapi-typescript src/api/openapi.json -o src/api/schema.d.ts
✨ openapi-typescript 7.13.0
🚀 src/api/openapi.json → src/api/schema.d.ts [52ms]
```

## Deviations from the prompt

**The verdict recorded here originates as Claude Code's recommendation,
adopted rather than independently authored from scratch.** The original
Update-8 brief said "I will write the verdict and the narration myself"; in
practice, Ikenna asked Claude Code to explain the open questions in plain
terms with recommendations, then said "go ahead with your recommendations."
v1.1 records this accurately - the reasoning is attributed to Claude Code, the
sign-off to Ikenna - rather than presenting the verdict as if independently
hand-written, because misattributing authorship on a document like this would
be its own small honesty failure.

## Flag for review

- The suggested demo narration (v1.1) is a draft script excerpt, not wired
  into any actual demo tooling (`prov demo rehearse`, the dashboard, or
  elsewhere) - no source file changed on this branch. If the narration is
  wanted inside the actual stage tooling, that is separate, explicitly-scoped
  work.
- Nothing about this decision is enforced by code: a future rerun of `prov
  graph adjudicate` against this same drop will still return whatever the
  adjudicator computes (`LIKELY_FAULT`, unchanged, since nothing about the
  pipeline changed) - this document records a demo-narrative decision, not a
  code change, and does not and should not alter what the pipeline reports.
