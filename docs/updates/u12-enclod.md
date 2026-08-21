# Update 12 — Enclod counter-repair reconciliation

Branch: `update-11-enclod`. Tag: `v1.0.13-update`.

**Naming deviation, flagged up front:** the prompt asked for doc
`u11-enclod.md` and tag `v1.0.12-update`. Both are already taken —
`docs/updates/u11-attention-overlay.md` and `v1.0.12-update` belong to the
attention-overlay update merged just before this one (branch
`update-10-attention-overlay`, PR #25). This repo's branch-number / doc-number
/ tag-number are already offset by one as of that update (branch "10" → doc
"u11" → tag "v1.0.12"), so continuing the actual sequence puts this update at
doc `u12`, tag `v1.0.13-update`. The branch name `update-11-enclod` was created
as literally instructed since it was free. Per the working agreement for these
reports, numbers below are copy-pasted from real command output, not retyped or
rounded by hand.

## Summary

Phase 1 swept exactly one of ten cumulative measure columns (`cars_60+`) and
found 0 resets, 0 dead counters. This update reruns counter repair over **all
ten columns × all 42 counters (420 series) across the full real archive**
(1,533,668 rows, 16 non-empty monthly files) and finds:

- **Resets under the existing heuristic: 3, not 80–96.** Sweeping every column
  does not recover the brief's expected count. See §1 and §3 — the shortfall
  is not an undercounting bug, the data genuinely does not contain a
  per-counter reset pattern.
- **Earlier months are not silently missing columns.** Exactly one file,
  `2025/01.csv`, lacks the measure columns, and it isn't a truncated
  file — it is completely empty (header only, 0 data rows). All 16 other files
  (2025/02 → 2026/05) carry the full column set with 100% non-null coverage.
  See §2.
- **What looks like a "backward step" in this data is not a device reset.**
  83% of all backward-step events land on a single calendar date
  (2026-05-24), hitting 39 of 42 counters and all 10 columns, with 384 of them
  at the *exact same timestamp* and a tight, proportional ~1.5% drop. This is
  the signature of a vendor-side batch correction across the fleet, not
  per-device resets. See §3.
- **Two counters do go silently dead — via a different signature than R21
  checks for.** `nLAUrPvFow5EmokJd4oc8H` and `8zeqGioF5wq6yV6YdzYMzN` each
  report normally for many months, then stop emitting rows entirely and never
  return, for the rest of the archive. Their own-span completeness (0.940,
  0.939) sits in the middle of the normal range and does not flag them — R21's
  whole-series-flatline check requires the counter to keep emitting a frozen
  value, and these counters stop emitting rows at all. See §4.

No headline number in this repo has been changed. No detector has been
retuned. The two open questions this leaves are in **§5 — escalated to you**.

---

## §1 — Which columns did phase 1 actually run, and what does a full sweep find?

Phase 1 (`schema_assumptions.yaml`, `observed_quality_notes`) ran counter
repair only on `cars_60+`. The full schema declares ten measure columns:
`cars_60+`, `vans_opposite_direction`, `vans_0-30`, `vans_30-60`, `vans_60+`,
`trucks_opposite_direction`, `trucks_0-30`, `trucks_30-60`, `trucks_60+`,
`uncategorized`.

Reran `provenance.io.counter_repair.repair_counter` for every (counter,
column) pair — 42 × 10 = 420 series — over each counter's full concatenated
series across all 16 non-empty files, sorted by time:

```
=== totals across ALL 10 measure columns, 42 counters ===
total (counter,column) series: 420
total resets (R05): 3
total nonmonotonic (R06): 566
total duplicates (R03): 97240
dead series (R21): 0

=== per-column totals ===
                           n_resets  n_nonmonotonic  n_duplicates  is_dead
column
trucks_0-30                       1              45          9724        0
trucks_opposite_direction         1              53          9724        0
vans_0-30                         1              51          9724        0
cars_60+                          0              64          9724        0
trucks_30-60                      0              49          9724        0
trucks_60+                        0              58          9724        0
uncategorized                     0              64          9724        0
vans_30-60                        0              58          9724        0
vans_60+                          0              66          9724        0
vans_opposite_direction           0              58          9724        0

=== completeness range across ALL (counter,column) series ===
min       0.198848
max       0.993747
```

**Finding: sweeping the other nine columns does not recover the brief's
~80–96-resets-per-column expectation.** The reset count barely moves (0 → 3
total, not per column), and duplicates scale exactly as expected — 9,724 per
column × 10 columns = 97,240, because a duplicate timestamp is a duplicate
*row*: the same incident is visible in every column of that row, not ten
independent incidents. Phase 1's `cars_60+`-only figure (9,724 duplicates, 63
non-monotonic) was representative of the whole archive's shape, not an
artefact of an incomplete sweep. §3 explains why the reset count stays low
even with every column included.

## §2 — Do earlier months carry count columns at all?

File-by-file header and non-null inventory, all 17 archive files:

```
       file  n_rows  n_header_cols  measure_cols_in_header  n_counters
2025/01.csv       0              5                       0           0
2025/02.csv   57615             15                      10          24
2025/03.csv   63965             15                      10          24
2025/04.csv   79778             15                      10          37
2025/05.csv   93224             15                      10          36
2025/06.csv   99000             15                      10          36
2025/07.csv   93552             15                      10          36
2025/08.csv   93563             15                      10          39
2025/09.csv   97868             15                      10          36
2025/10.csv  104823             15                      10          36
2025/11.csv  101880             15                      10          36
2025/12.csv  104907             15                      10          36
2026/01.csv  104803             15                      10          36
2026/02.csv   90481             15                      10          37
2026/03.csv  114135             15                      10          41
2026/04.csv  114621             15                      10          40
2026/05.csv  119453             15                      10          40
```

No file has a partial column set with hidden nulls — every file that carries
the ten measure columns has 100% non-null coverage on all of them (checked
column-by-column against row count).

**Finding: refutes the "earlier months carry no columns" theory as originally
framed, confirms it for exactly one file.** `2025/01.csv` is not a truncated
early-schema file — it is empty outright (header row, zero data rows), already
recorded in `schema_assumptions.yaml` as a structural absence. Every other
month from the very start of the archive (2025-02) carries the full column
set. The counter count growing from 24 to 41 counters across the archive
reflects real devices coming online over time (see §4), not a schema change.

## §3 — Is the reset pattern shaped differently than "drop to ≤50%"?

Characterized every backward step (`value[i] < value[i-1]`) in each counter's
own deduplicated, time-sorted series — the same series `repair_counter`
operates on — across all 420 series:

```
=== ratio (current/previous) distribution, n=559 ===
min         0.307874
50%         0.985351
99%         0.994783
max         0.997183

ratio<=0.5 (R05 under current heuristic): 3
ratio>0.5  (R06 under current heuristic): 556

ratio < 0.05: 0
ratio < 0.01: 0
cur == 0 exactly: 0

=== gap in 15-min intervals before each backward step ===
min 1.0 / 50% 1.0 / max 1.0   (always exactly one tick — never after a gap)

=== land on a month boundary (day 1, 00:00)? ===
0 / 559
```

(559, not the sweep's 569 (566 R06 + 3 R05): one counter,
`gh9d5GPy764KFLjmCrjnbG`, has ten rows of its May-2026 file locally
out-of-chronological-order — `repair_counter` sorts after deduplicating and
correctly resolves them into ten small R06 steps; this characterization
script sorts first, which silently absorbs that reordering instead of
surfacing it as backward steps. A separate, minor, single-counter,
single-file R04-shaped artifact, not part of the pattern below — the sweep's
566/3 are the authoritative per-column totals cited elsewhere in this
document.)

There is **no near-zero cluster anywhere in this data.** A true counter reset
— a device restarting its onboard cumulative total — would show up as a ratio
near 0 (or `cur == 0`). None exists: the minimum ratio across all 559 events
is 0.308, and the distribution is overwhelmingly concentrated at 0.90–1.00
(median 0.985, i.e. a ~1.5% dip). Every backward step happens between two
immediately-consecutive 15-minute rows — never after a data gap, never at a
device-restart-shaped boundary, never at a month boundary.

**What the "backward steps" actually are:** a single-day, near-fleet-wide
correction, not per-device noise.

```
=== dates with >=5 backward-step events ===
2026-05-24    464   (39 of 42 counters, all 10 columns)
2026-02-05     58
2026-02-04     14
2025-09-22      8
2025-04-03      7
2025-02-03      5

=== the 2026-05-24 10:00:00Z instant alone ===
n events: 384
ratio:  min 0.929 / 50% 0.986 / max 0.996, std 0.005   (tight, proportional)
```

83% of all backward-step events (464 / 559) fall on 2026-05-24; 384 of those
land at the *exact same 15-minute timestamp* (10:00:00Z) across 39 counters
and all 10 columns, each dropping by a tightly clustered ~1.5% (std 0.005) —
proportional to that series' own magnitude (absolute drops range 1 to 58,398
vehicles, scaling with the series). A second, smaller cluster sits on
2026-02-04/05 (72 events). Two of the three ratio≤0.5 events are inside that
February cluster; the third is inside a small 2025-04-03 cluster. Fewer than
25 events, out of 559, fall outside these dated clusters.

**Finding: the shape isn't a differently-calibrated reset — it isn't a
per-counter reset at all.** A proportional, near-simultaneous drop across
nearly the whole fleet at one instant is the signature of a vendor-side batch
correction or re-export (a dedupe/rebase pass touching the whole archive at
once), not sensor-level resets. **I have not added a second reset-detector
variant.** The instruction was to add one only if the heuristic needs
retuning for a genuine second reset population; there isn't one here — R06 is
already the correct classification for every one of these events, and the 3
that cross the existing ≤50% line are themselves inside the same systemic
clusters, not standalone device resets that the threshold is misplaced
against. Whether a *new, non-reset* detector for "simultaneous cross-fleet
correction" is worth building is a separate design question — see §5.

## §4 — Are the two silently-dead sensors findable another way?

R21 (whole-series flatline: `max == min` across the *entire observed span*)
found 0 dead series across all 420, confirming phase 1. That check requires
the counter to keep emitting rows with a frozen value for its whole recorded
life — it cannot see a counter that simply **stops emitting rows at all**.

Compared each counter's last observed row against the archive's global last
timestamp (2026-06-01 00:00Z, the tail of the May 2026 file):

```
Counters silent for >= 1 week (672 intervals) before the archive's last timestamp:
                  uuid  n_rows  n_files                 last_seen  intervals_silent  files
nLAUrPvFow5EmokJd4oc8H   27572       10 2026-02-01 00:00:00+00:00           11520.0  04,05,06,07,08,09,10,11,12,01
8zeqGioF5wq6yV6YdzYMzN   31619       12 2026-03-18 00:00:00+00:00            7200.0  04,05,06,07,08,09,10,11,12,01,02,03
```

Every other counter (40 of 42) has `intervals_silent_before_archive_end == 0`
— still reporting through the archive's last row. These two are a sharp,
unambiguous split from the rest, not a borderline call:

- **`nLAUrPvFow5EmokJd4oc8H`** reports for 10 consecutive files (Apr 2025 →
  Jan 2026, 27,572 rows), stops cleanly at the January/February 2026 file
  boundary, and never reports again — 11,520 intervals (~120 days: Feb, Mar,
  Apr, May 2026) of total silence through the end of the archive.
- **`8zeqGioF5wq6yV6YdzYMzN`** reports for 12 consecutive files (Apr 2025 →
  Mar 2026, 31,619 rows), stops **mid-month** on 2026-03-18 (not at a file
  boundary — a real stop, not a filing artefact), and never reports again —
  7,200 intervals (~75 days) of silence through the end of the archive.

**Their own-span completeness hides them.** `_completeness()` measures
observed-vs-expected only within a counter's own first-to-last observed span,
so a counter that permanently stops still looks "complete" over the days it
was alive:

```
nLAUrPvFow5EmokJd4oc8H own-span completeness (all 10 columns): 0.9398
8zeqGioF5wq6yV6YdzYMzN own-span completeness (all 10 columns): 0.9387
overall completeness distribution excluding these two: min 0.199 / max 0.994
```

Both sit squarely inside the normal 0.20–0.99 range phase 1 already reported
— indistinguishable from a healthy counter by that metric, exactly as the
brief's phrasing anticipated ("wide enough to hide one").

**Ruled out the alternative signature (flatline at a non-zero value) as the
mechanism for these two.** There *are* long interior flatlines in this data —
364 (counter, column) series have a flat run of a day or more where the
counter keeps emitting rows but a single column's cumulative value freezes.
But they don't correspond to device failure: within a given counter, these
flatline windows land on different, non-overlapping dates per column. Counter
`HohTwWyxcfX9nBKqJpnwd7`, for example, has six separate flatline windows
spread from May 2025 to April 2026, no two overlapping. A dead *device* would
freeze every column of a counter at once; nothing in the 42 counters does
that. These flatlines read as genuine zero-throughput stretches for narrow
vehicle-class columns (`trucks_0-30`, `vans_opposite_direction`, etc. — minor
classes where a week of zero events on one road segment is physically
plausible), not sensor faults.

**Finding: "two silently dead sensors" is a real, sharply-identifiable
pattern in this data — but the mechanism is full-row dropout (the counter
stops sending anything, forever), not a frozen value inside continuing rows.**
R21 as coded cannot see this because it requires the counter to still be
present in the frame. Whether to add a detector for it is escalated below.

## §5 — Escalated to you

1. **Should a new detector be added for "permanent dropout"** — last observed
   row precedes the archive's global end by more than the dead-sensor
   threshold (672 intervals / 1 week), with no subsequent row at all? This is
   the mechanism behind the two counters in §4, and it's a materially
   different check from R21 (which needs the counter to still be emitting
   rows). I did not add it — the task authorized a new detector only for a
   reset-heuristic *variant*, and this is a dead-sensor question, not a reset
   one. If you want it, it needs a name in the reason-code registry, a
   threshold decision (same 672-interval basis as R21, or its own), and a
   decision on whether it belongs in `io/counter_repair.py` next to R21 or is
   a separate coverage-model concept (a counter's expected-vs-observed frame
   ending early looks structurally like the coverage model's own absence
   logic, not like a per-row detector).
2. **Should the fleet-wide correction event (§3) get its own flag?** 464 of
   559 backward-step events are one proportional, near-simultaneous
   correction across 39 counters — arguably more interesting for a trust
   layer to surface ("the vendor rewrote ~1.5% of the fleet's history on this
   date") than to leave folded into 464 individual R06 rows. This would be a
   genuinely new category (a cross-series, single-instant pattern), not a
   retuned reset threshold, and is a bigger design conversation than this
   reconciliation pass.
3. **`thresholds.yaml`'s comment for `dead_min_consecutive_intervals`** reads
   "Two Enclod counters are dead this way" as a stated fact. That comment was
   written at phase 0 (commit `eb73df2`, before any real data existed) and
   describes the brief's expectation, not a verified finding — R21 as coded
   has never found either of the two counters this update did find (they're
   dead by a different mechanism; see §4). Worth rewording regardless of
   what's decided on point 1, so the comment doesn't read as settled fact
   ahead of the config it's attached to actually catching it.

## What was changed in this branch

- `schema_assumptions.yaml`'s `enclod_traffic.observed_quality_notes` updated
  from the `cars_60+`-only figures to the full 420-series sweep (§1), with the
  new dead-counter-by-dropout finding (§4) added alongside the existing
  `resets_found` / `dead_counters_found` fields, which are unchanged in
  meaning (still R05 / whole-series R21) but now reflect the complete sweep
  rather than one column.
- This document.
- `tests/fixtures/golden/audit.md` regenerated. The `schema_assumptions.yaml`
  edit above changes the config hash `audit.md` renders in its header line
  (unrelated to Enclod - it hashes the whole config file), which drifted the
  committed golden snapshot; `test_audit_md_matches_golden` caught it exactly
  as designed. Confirmed via diff that the config-hash line is the *only*
  line that changed. Regenerated by calling the same
  `generate`/`run_audit`/`render_markdown` path the test itself uses, checked
  byte-identical across two runs before committing (standing rule 8).
- No change to `counter_repair.py`, `thresholds.yaml`, `reason_codes.py`, ADR
  0005, or the phase-1 report. No detector retuned. No headline number
  changed.

## Test gate

`make check`: green — 680 passed, 2 deselected, coverage 90.81% (floor 88%),
frontend contract current. One failure surfaced on the first run before the
fixes above: `test_audit_md_matches_golden`, caused by the config-hash drift
described above, resolved by regenerating the golden file (not by touching
the test). Its own failure message points at a
`tests.fixtures.golden.regenerate` module for exactly this situation; that
module does not exist anywhere in the repo — a pre-existing gap, unrelated to
this branch, worth a follow-up but out of scope here.
