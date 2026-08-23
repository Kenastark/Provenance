# Update 23 — implementing the six escalated decisions

Branch: `update-23-headline-decisions`. Tag: `v1.0.24-update`.

Follow-up to `u22-headline-reconciliation.md`, which escalated six decisions. Ikenna
reviewed the recommendations and asked for all six to be implemented as recommended.
**Five are done. One (Q6) is blocked on an input I do not have**, and is reported rather
than worked around.

Unlike u22, this branch *does* change code and configuration-adjacent wording. It still
changes **no detector, no threshold, and no number the audit engine produces** — verified
below by re-running the audit and diffing the golden report.

---

## Q1 — Which completeness figure goes on the slide ✅ DONE

**Decision implemented: conventional completeness, 100.0000%**, with grid completeness
(85.7374%) documented as the immediate follow-up answer rather than hidden.

Rationale, restated so the choice is auditable: it is the measure Green Sentinel itself
reports; it is a *larger* number than the 99.95% it replaces, so it is not a climbdown;
and it puts the two headline figures on disjoint denominators, which removes the
double-counting objection entirely.

Changed:

- **`CLAUDE.md`** — the thesis paragraph. `roughly 99.95% completeness` →
  `100.00% conventional completeness`, plus a new paragraph stating both measures with
  their denominators and recording explicitly that ~99.95% was the synthetic corpus's
  grid completeness and is no longer quoted anywhere. Edited in place deliberately:
  `CLAUDE.md` is the rulebook, not a versioned `docs/` document, and standing rule 10
  governs the latter.
- **Four demo documents**, as new versions (rule 10 — the v1.0 files are untouched):
  `demo-script-v1.1-real-data.md`, `judge-questions-v1.1-real-data.md`,
  `one-page-description-v1.1-real-data.md`, `video-storyboard-v1.1-real-data.md`.
  Each opens with a table of what changed from v1.0 and why, with the superseded value
  struck through rather than deleted.
- **`docs/demo/README.md`** — now says which versions are current and why v1.0 must not
  be read from on stage.

### ⚠️ A second, worse error found while doing this

The demo script and the video storyboard **stated the wrong verdict for the KER11 event**.
Both said `AMBIGUOUS`, *routed to human review*. The real drop returns **`LIKELY_FAULT`,
high confidence, and it does not route to review** (u22 §4). The AMBIGUOUS claim described
the synthetic corpus's top event and was written before the real export was loaded.

This was not one of the six decisions. It was found because implementing Q1 required
opening those files. It would have been said out loud on stage. Both v1.1 files correct
it and flag it in their change tables.

Two further v1.0 figures were corrected the same way:

| Where | v1.0 | v1.1 | Basis |
|---|---|---|---|
| Script B3 / storyboard shot 5 | trust `0.577 → 0.275` | **`0.7347 → 0.4308`, T04 appears** | The real stored trust series, queried below. |
| Storyboard shot 2 | `18 monitoring points` | `16 stations` | The audit's own `n_stations`. Both framings are defensible (CLAUDE.md counts 16 land + 2 water); v1.1 notes the ambiguity rather than silently picking. |

The real trust series, read from the loaded database:

```
$ .venv/bin/python -c "<async read of trust_scores via provenance.io.db.engine>"
(datetime.datetime(2026, 6, 1, 11, 0), Decimal('0.7322'), ['T01', 'T06', 'T03'])
(datetime.datetime(2026, 6, 2, 11, 0), Decimal('0.7347'), ['T01', 'T06', 'T03'])
(datetime.datetime(2026, 6, 3, 11, 0), Decimal('0.4308'), ['T01', 'T06', 'T03', 'T04'])
(datetime.datetime(2026, 6, 4, 11, 0), Decimal('0.4408'), ['T01', 'T06', 'T03', 'T04'])
```

T04 (`TRUST_IMPLAUSIBLE_VALUE`) appears on 2026-06-03 and not before. Trust scores are
stored per station per day at 11:00, so the 20:00 event on 06-02 lands in the window
ending 06-03T11:00 — the timing is consistent, and v1.1's wording says "across that day"
rather than "the moment it lands", which the daily cadence does not support.

**Also flagged, not fixed:** v1.0's offline-corpus figures ("75,585 readings, 2.906%
defect rate") disagree with `u6-real-drop.md`'s measured synthetic figures (35,265
readings, 2.9620%). Different fixture invocations; nobody has reconciled them. v1.1
carries the discrepancy forward as a flag and tells the operator to run
`prov demo rehearse` before relying on either. Not resolved here — it is offline-fallback
material and does not touch the on-stage story.

---

## Q2 — Volunteer the R01 split ✅ DONE

**Decision implemented: say it in the same breath as the headline, not in reserve.**

The B1 block of `demo-script-v1.1` now states 29.1% and then immediately splits it:
48.97% never arrived, the other 15.4% arrived and is wrong. `judge-questions-v1.1` adds
**Q14** as the prepared answer if a judge gets there first, and rewrites **Q2**, whose
v1.0 answer was factually wrong:

> **v1.0's Q2 claimed** the defect rate asks "of the *present* cells, how many are wrong?"
> It does not. Its numerator includes 24,900 `ROW_ABSENT` cells — 48.97% of it. The old
> answer denied a fact printed on our own audit report.

The one-pager now leads with both halves.

---

## Q3 — R10 counted per reading, named as one systemic finding ✅ DONE

**Decision implemented: keep it in the rate, and present it as a capability rather than
defend it.**

The rate is unchanged (the unit of trust is the reading, so 10,627 untrustworthy CO2
readings are 10,627 defective cells). What changed is that the demo material now *leads*
with the network-wide framing instead of waiting to be challenged: `demo-script-v1.1`'s
B1 block points at the `network_wide_findings` row and says the engine reports it as one
systemic fact, not 10,627 independent faults. `judge-questions-v1.1` **Q15** is the
prepared answer, and **Q16** and **Q17** cover the two adjacent objections (station
concentration; PM10 being a clean channel).

No detector, threshold, or config value was touched. The engine already emitted the
network-wide finding — this is a narration change only.

---

## Q4 — Outage events say why, instead of reading as "pending" ✅ DONE

**Decision implemented: fix the display, record the reason, and do *not* fold it into
AMBIGUOUS.**

The problem: five stored events (all `R02` communication outages) kept `verdict = NULL`,
and the dashboard rendered "pending adjudication" for them — telling the operator to run
a command they had already run, about events that were in fact settled.

The cause, confirmed in `graph/replay.py::build_candidate`: an outage has **no reading at
its own timestamp**, so there is no rise for the wind to carry and the plume test cannot
apply. `adjudicate_stored_events` was silently `continue`-ing past them.

### Backend — `src/provenance/graph/persist.py`

A skipped event now records **why**, under `Event.evidence["adjudication_not_applicable"]`,
so the two meanings of a null verdict stay distinguishable:

- no record → not adjudicated yet;
- a record → adjudicated over, and the plume test does not apply.

The reason is **derived from the frame** (is the parameter carried at all? is there a
reading at that timestamp?), mirroring `build_candidate`'s own two `None` paths. No reason
code is named in the logic — standing rules 1 and 2.

`adjudicate_stored_events` now returns a `SweepResult(adjudicated, not_applicable)` rather
than a bare int, because "we judged 19" and "we judged 19, and the other 5 had no plume
question" are different statements. The record is cleared if an event later becomes
adjudicable, and a stale `adjudication` bundle is cleared if it stops being one.

**AMBIGUOUS was deliberately not reused.** AMBIGUOUS means *we are unsure, route this to a
human*; we are not unsure about an outage. Overloading it would erode the one signal that
makes AMBIGUOUS worth having. Pinned by a test.

### Against the real drop

```
$ .venv/bin/prov graph adjudicate-db --source data/raw
Adjudicated 19 stored event(s); verdicts written.
5 event(s) had no rise to propagate (no reading at the event time); the plume
test does not apply and each carries a recorded reason rather than a verdict.
```

```
DEB-KER04 TVOC 2026-05-27 22:00:00 verdict= None
    {"basis": "no_reading_at_event_time", "reason": "There is no TVOC reading at DEB-KER04 for 2026-05-27T22:00:00, so there is no rise for the wind to carry and nothing for the downwind neighbours to corroborate. The plume test does not apply; this is not an unsettled call."}
DEB-KER01 TVOC 2026-05-27 23:00:00 verdict= None
DEB-KER18 TVOC 2026-05-29 11:00:00 verdict= None
DEB-KER05 TVOC 2026-05-27 23:00:00 verdict= None
DEB-KER07 TVOC 2026-05-29 23:00:00 verdict= None
```

All five are TVOC communication gaps, exactly as u22 predicted.

### Frontend

- `lib/adjudication.ts` — `parseNotApplicable()`, defensive like `parseAdjudication()`.
- `lib/verdict.ts` — `verdictMeta()` takes an optional second argument and gains a
  `not_applicable` kind labelled "No plume test — not applicable". `routesToReview` stays
  `false`.
- `features/timeline/EventTimeline.tsx` — `VerdictChip` accepts the event's evidence; the
  detail pane shows the backend's recorded reason instead of the "run `prov graph
  adjudicate-db`" message.

**No API contract change.** `evidence` was already a free-form JSON map on `EventOut`, so
`gen_frontend_contract.py --check` and `pnpm gen:types` are both clean.

### Deliberately not done

The **Alert Centre** still shows "pending adjudication" for such an event. `AlertItem`
carries no `evidence` field, and widening the alerts contract to fix a chip on a surface
these events rarely reach was not worth the drift. Noted below as a residual.

Also **not** changed: `ops/alerts.py:60` treats a null verdict as `_UNADJUDICATED_GENUINENESS`
when ranking risk. That is now slightly wrong for a not-applicable event — but changing it
would alter alert *rankings*, which is a scoring change, not the display fix that was
authorised. Left alone deliberately.

---

## Q5 — The "hour" wording in the defect-rate definition ✅ DONE

**Decision implemented: fixed, with the golden fixture regenerated.**

`DEFINITION` in `src/provenance/grid/defect_rate.py` described a covered cell as
`(station, parameter, hour)`. 300 of the 174,583 covered cells are **daily** (the two LAEQ
noise series). The arithmetic was always per-cadence; only the sentence was loose — and
that sentence renders verbatim into `audit.md`, `audit.html` and the `/v1/export` payload,
where a careful judge would read it.

Now: `(station, parameter, tick) ... the tick being that series' own measured cadence,
hourly or daily, never assumed`. The module docstring says the same.

The golden snapshot was regenerated inline (the `regenerate` module its error message
names does not exist — see [[golden-fixture-config-hash-gotcha]]). **Exactly one line
changed**, which is the proof that no computed number moved:

```
--- old
+++ new
@@ -15,3 +15,3 @@
-> defect rate = ... a covered cell is one (station, parameter, hour) the station actually measures, and a ...
+> defect rate = ... a covered cell is one (station, parameter, tick) the station actually measures - the tick being that series' own measured cadence, hourly or daily, never assumed - and a ...
```

A regression test (`test_definition_does_not_claim_every_cell_is_an_hour`) pins the
wording so it cannot drift back.

`config_hash` is unaffected — it hashes the YAML config files, not Python source — so the
audit's own metadata is unchanged.

### The audit is byte-identical after all of the above

```
$ .venv/bin/prov audit run --data data/raw --out reports
149,683 readings  conventional completeness 100.0000%
50,843 defective cells  defect rate 29.1225%
  R01  ROW_ABSENT                   24,900
  R02  COMM_GAP                     939
  R07  EXCEEDS_PHYSICAL_MAX         1
  R09  CROSS_PARAM_INVERSION        100
  R10  UNIT_INCONSISTENT            10,627
  R11  DETECTION_LIMIT_FLOOR        2,111
  R12  ZERO_VARIANCE                12,194
  R13  LOW_VARIANCE_DEGRADED        5,622
  R14  STEP_CHANGE                  236
  R18  PARAMETER_ABSENT_STRUCTURAL  2
  R19  SOURCE_ABSENT                3
  R21  SENSOR_DEAD                  3
```

Identical to u22 and to `u6-real-drop.md`. No detector, threshold, or number moved.

---

## Q6 — Commit the blueprint ⛔ BLOCKED

**Not done, because I do not have the document.**

The recommendation was for *Ikenna* to commit `is-this-real-blueprint-v1.0/1.1/1.2` to
`docs/`. That is an action only he can take: as u22 §Part 5 established, the file exists
nowhere in this repository, nowhere in its git history, and nowhere under
`/Users/ikenna/Documents`. Re-confirmed on this branch:

```
$ find . -iname "*is-this-real*" -o -iname "*blueprint*" | grep -v node_modules | grep -v .venv
(no output)
```

I have not written a substitute, and I will not — inventing the v1.2 text in order to
"supersede" it would produce exactly the untraceable assertions standing rules 1 and 2
exist to prevent, and would make u22's Part 5 item 6 ("leave untouched any `⚠️` marker
Parts 1–4 did not resolve") impossible to honour.

**What is ready.** Everything v1.3 needs as input is assembled: measured values with their
denominators (u22 Parts 1–3), the settled KER11 evidence (u22 Part 4), the changed-since
note for the completeness figure, and the three candidate headline sentences (u22 Part 5).
Commit v1.2 or paste its text and v1.3 becomes a mechanical merge in a follow-up branch.

---

## Test gate

```
$ make check
```

Full output in the section below. Also re-run with `data/` emptied, per standing rule 7.

Frontend: `pnpm test:coverage`, `pnpm exec tsc --noEmit`, and the contract gate
(`gen_frontend_contract.py --check` + `pnpm gen:types` + `git diff --exit-code`) all
clean — no contract drift, as expected for a change that only reads an existing
free-form `evidence` map.

---

## Residuals — things a human should look at

1. **The Alert Centre still says "pending adjudication"** for a not-applicable event
   (`AlertItem` has no `evidence` field). Fixing it means widening the alerts contract.
   Worth doing only if such an event can realistically surface there.
2. **`ops/alerts.py` risk weighting** treats a not-applicable verdict as unadjudicated.
   Deliberately untouched — changing it moves alert rankings, which was not authorised
   here.
3. **The offline-corpus figures** (75,585 readings / 2.906%) still disagree with
   `u6-real-drop.md` (35,265 / 2.9620%). Carried forward as a flag in the v1.1 docs, not
   resolved.
4. **"16 stations" vs "18 monitoring points"** — both defensible, and the two are used in
   different assets. v1.1 notes it; somebody should pick one and apply it everywhere.
5. **Q6 remains open** and blocks blueprint v1.3.
6. **The final stage wording is still Ikenna's.** Q1 settled *which completeness figure*
   is used, and `demo-script-v1.1` writes lines around it — but u22's three candidate
   headline sentences were explicitly reserved for him, and nothing here overrides that.
   The script's cold open is a working draft built from the chosen figure, not a decision
   about the opening sentence.
