# Update 8 — evidence assembly for the KER11 ~4,100 µg/m³ PM10 event

Branch: `update-8-ker11`. Tag: `v1.0.9-update`.

Per the working agreement for these update reports: what follows is copy-pasted
or directly quoted from a real command's stdout, not retyped or rounded by hand
beyond what the tool itself already rounded.

## What was built

**`docs/adjudications/ker11-4100-evidence-v1.0.md`** — the B3 demo's centrepiece
event, the ~4,100 µg/m³ PM10 reading at DEB-KER11 (2026-06-02T20:00:00), has
never had a single document assembling everything the system itself can say
about it. This is that document: every reason code the audit engine attaches to
the reading, DEB-KER11's other parameters and every neighbouring station in the
surrounding hours (ranked by distance), the wind field at that hour, the full
analytic propagation-adjudicator bundle, a genuine `--learned` (HST-GAT)
contrast, a check for any maintenance window/calibration event/outage overlap,
and a second, independently assembled candidate event as a backup. **It reaches
no verdict** — every one of its 8 sections is either a `$ prov ...` command's
verbatim output or a labelled read against the same public library functions
the CLI itself calls, and a 9th section ("What I did not decide") lists the
interpretive questions left open for a human. Per the brief, that person's
decision becomes `ker11-4100-evidence-v1.1.md`; nothing of that kind is written
here, in any commit message, or anywhere else in this branch.

To make §6 (the learned-path contrast) a genuine comparison rather than a
graceful-degradation stub, an HST-GAT artefact was trained fresh against
`data/raw` (`prov models train-hstgat --source data/raw`, 3,299 parameters,
conformal coverage 0.9 nominal → 0.8708 empirical, n=2,816) — none existed
before this branch. The artefact and its auto-generated card are gitignored,
as designed (`hst-gat-v1-8f8efeed.{pt,card.json}`,
`docs/model-cards/hst-gat-v1-8f8efeed.md`); nothing about training or using it
required touching source code.

### What the assembled evidence actually shows, in outline (not a verdict)

- The reading is the network's only `R07 EXCEEDS_PHYSICAL_MAX` in 149,683
  readings, and DEB-KER11 itself carries no other reason code — outage,
  step-change, or otherwise — anywhere in a ±24h window around it.
- It is not a single-hour blip: PM10 rises for one hour beforehand and decays
  over three hours afterward, and PM2.5 echoes it a smaller, one-hour-delayed
  amount.
- None of DEB-KER11's 15 neighbouring stations move at all, including the
  nearest one (1.39 km) and all five the wind-cone model calls downwind.
- The wind reading the propagation adjudicator depends on comes from a single
  station-local instrument during an hour when the other 14 reporting
  stations' own wind readings span nearly the full compass at mostly
  sub-5-km/h speeds — a network-wide calm, directionally-incoherent hour.
- The analytic adjudicator returns `LIKELY_FAULT`, confidence 1.00 (high).
  A freshly trained HST-GAT, run as `--learned`, reaches the **same verdict**
  but expects **no propagation at all** at any of the five neighbours (vs. the
  analytic prior's hundreds-to-thousands of µg/m³), each with a calibrated
  interval that comfortably contains the observed near-zero change.
- No R15 calibration detector exists to check, and no maintenance-window or
  calibration-log data source exists anywhere in the real drop — this reads
  as "un-checkable," not "clean."

## Test gate

`make check` (`lint` — ruff check, ruff format --check, mypy --strict — then
`test` — the full pytest suite — then `web-contract-check`):

```
$ ruff check src tests            # clean, no output
$ ruff format --check src tests   # clean, no output
$ mypy                             # clean, no output
$ pytest
[... per-file coverage table elided (176 files) ...]
------------------------------------------------------------------------------------------
TOTAL                                           7460    524   1410    211    91%
Required test coverage of 88% reached. Total coverage: 90.65%
========== 673 passed, 2 deselected, 34 warnings in 381.54s (0:06:21) ==========
$ python scripts/gen_frontend_contract.py --check
Frontend contract is current.
$ cd apps/web && pnpm gen:types && git diff --exit-code -- src/api/schema.d.ts
> @provenance/web@0.0.1 gen:types
> openapi-typescript src/api/openapi.json -o src/api/schema.d.ts
✨ openapi-typescript 7.13.0
🚀 src/api/openapi.json → src/api/schema.d.ts [60.9ms]
[exited with code 0]
```

No source file changed on this branch, so `web-contract-check`'s frontend-drift
comparison had nothing to drift against; it passed as a no-op. Only
`docs/adjudications/ker11-4100-evidence-v1.0.md` and this report are new,
tracked files — everything else this branch touched (the trained HST-GAT
artefact, `reports/audit.json`, `reports/adjudications*/`,
`data/manifests/observed-schema-*.json`) is gitignored, confirmed with
`git status` before committing.

## Deviations from the prompt

1. **Trained a real HST-GAT artefact rather than reporting the graceful
   degradation.** The prompt asks for "the learned path's output (`--learned`)
   for contrast" — with no artefact present, `--learned` would have silently
   produced the analytic result twice, which is not a contrast. Training one
   (CPU-only, ~4m45s, gitignored output) is what makes §6 an actual comparison.
2. **The prompt's phrase "the next best-corroborated large event" does not
   describe anything in this drop.** Ranking the same way `prov graph
   adjudicate --limit 10` does, rank 2 through 5 are all `AMBIGUOUS` at the
   identical capped confidence (0.50) — none of them is "well-corroborated,"
   including the one used as the second case. Ranks 6–10 are a zero-magnitude
   `WaterLevel` tie at DEB-KER03, not five more large events. §8 of the
   evidence document uses rank 2 (DEB-KER06/CO) because it is the pipeline's
   own next-ranked non-degenerate candidate — chosen by the same ranking the
   demo runs, not hand-picked for a cleaner story — and says so explicitly
   rather than silently presenting it as well-corroborated when it is not.
3. **`station_zones.yaml`'s curated zone classification (industrial/urban/…)
   is deliberately not cited anywhere in the evidence document**, even though
   both events' stations have entries there. That file is explicitly marked
   `status: provisional`, "human curation, not a measurement" — citing it would
   have smuggled an interpretive judgment into a document the brief asked to
   contain only things derived from data. The raw `Location` column string
   (site name + coordinates) is used instead, since that is literally in the
   data.

## Flag for review

- **There is no well-corroborated second large event anywhere in this drop's
  top 10 ranked candidates.** See deviation 2 above. If the B3 demo block
  needs a second case that a human would read as "the system got this one
  right" rather than "the system correctly couldn't test this one," it is not
  in this ranking — it would have to come from further down the list, from a
  different ranking criterion entirely, or the demo narration would need to
  say plainly that its backup case is one the adjudicator could not test
  (calm wind at the source), which is itself an honest and arguably more
  interesting beat.
- **The learned-path contrast (§6) agrees with the analytic verdict but
  disagrees almost completely on the underlying physics** — the HST-GAT
  expects essentially zero propagation for an event like this, the analytic
  plume prior expects a large one, and both end up uncorroborated. Whether
  that convergence-for-different-reasons is worth surfacing on stage, and how,
  is a demo-narrative call the evidence document deliberately leaves open
  (§9.5).
- Everything else this document surfaced as open is listed in its own §9
  ("What I did not decide") rather than duplicated here.
