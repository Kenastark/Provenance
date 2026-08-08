# 0005 - Enclod traffic counters: canonical mapping

**Status:** Accepted (2026-08-08)

## Context

Phase 1 built reset-aware counter repair (`io/counter_repair.py`) and phase 2 built
the ingestion abstraction (ADR 0003), which leaves the Enclod adapter deliberately
*discover-only*: `read()` raises rather than invent a schema. Phase 4 wants this
data for wind-conditioned attribution, so the mapping has to be settled before
someone reaches for it under deadline pressure.

Profiling the real archive turned up a problem with the assumption block itself,
not just with the missing values in it. `schema_assumptions.yaml` declared
`timestamp_column` / `counter_column` / `value_column` — a **narrow** shape, one
counter and one value per row. The real archive is **wide**:

```
time, uuid, nick, lat, lng, cars_60+, vans_opposite_direction, vans_0-30, ...
```

One row per (counter, 15-minute tick), carrying a cumulative total for each vehicle
class in its own column. 17 monthly files, ~1,533,668 rows, 42 counters identified
by `uuid`. Ten measure columns, stable from 2025-02 to 2026-05.

So confirming this source is not "fill in three names". It is a change to the shape
of the assumption, and then a decision about what a counter *is* in canonical terms
— which is expensive to reverse once readings, defects, and trust scores are keyed
on it in the database.

## Decision

**A counter is a station. A vehicle class is a parameter.**

| Canonical field | Enclod source |
|---|---|
| `station_id` | `uuid` (42 distinct) |
| `parameter` | the measure column name, e.g. `trucks_60+` |
| `timestamp_utc` | `time`, parsed as UTC |
| `value` | per-interval count, after reset-aware differencing |
| `unit` | `vehicles/15min` — **derived, not observed** (see below) |
| `source_file` | the monthly CSV |

The alternative — one station per (counter, class) — was rejected: it would
multiply 42 stations into 420, break the "a station is a physical place" meaning
that `stations.geometry` and the map both rely on, and make cross-parameter checks
between classes at the same site impossible.

Three consequences follow, and they are the reason this is an ADR:

1. **Every phase-1 detector works unmodified.** Frozen counters, absent rows,
   duplicate timestamps, and step changes are all defined over (station, parameter,
   time) and need no traffic-specific code. The coverage model's structural-absence
   inference also transfers: a counter that never reported a class is a coverage
   fact, not a defect.
2. **`value` is a differenced quantity, not a raw reading.** The canonical frame
   carries per-interval counts; the cumulative total is an artefact of the vendor's
   transport. R05/R06 are emitted by the repair step, which is the only place that
   ever sees the running total.
3. **The unit is derived.** The source declares no unit anywhere. Standing rule 2
   forbids inventing one at a call site, so the label is written down in
   `schema_assumptions.yaml` as `derived_unit` and marked as derived.

## What is deliberately NOT done here

`enclod_traffic.status` is set to **`observed`**, not `confirmed`. The columns are
written down; the parse is not implemented. `io/ingest/enclod.py` keeps refusing to
read, and `test_enclod_fails_loudly_while_columns_are_unconfirmed` keeps passing.
Promoting to `confirmed` is the same commit that wires the parse — never a config
edit on its own, because a config edit alone would open the gate onto code that
does not exist.

## Open question for whoever wires this

The competition brief describes "~80-96 resets per column" and "two silently dead
sensors". A sweep of `cars_60+` across all 42 counters found **neither**: zero
resets, zero dead counters, but 9,724 duplicate timestamps, 63 non-monotonic runs,
and per-counter completeness ranging 0.24 to 0.99.

Do not assume the brief is wrong. Three explanations are open, and they are
distinguishable with an afternoon's work:

- Only one of ten measure columns was swept. Resets may live in the others.
- The reset heuristic is "drop to <= 50% of the previous total". A counter that
  restarts at an arbitrary non-zero value would read as R06, not R05 — and 63
  non-monotonic runs is suspiciously close to the brief's order of magnitude.
- Rampant duplicate timestamps mean the feed re-sends rows. Dedupe-then-difference
  may be smoothing over restarts that a different ordering would expose.

Settle this before phase 4 builds attribution on top of these counts. A defect rate
computed over a source whose repair step is mis-calibrated is exactly the kind of
number this project exists not to publish.

## Consequences

- Phase 4 starts from a decided mapping instead of rediscovering the file shape.
- The narrow-shape keys are gone, so nobody implements against them by mistake.
- The reset discrepancy is recorded as an open question with a plan, rather than
  surviving as a footnote in a phase report nobody re-reads.
