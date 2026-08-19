# Trust Score methodology — v1.1 (invariants, series, station geo)

**Status:** Current. **Supersedes** `trust-score-methodology-v1.0.md`.
**Scope:** Unchanged from v1.0 — the phase-2 statistics-only Trust Score, no ML.
This revision records three things that came out of the phase-2 flag review; the
score's definition, components, weights, and Risk are exactly as in v1.0.

## What changed since v1.0

### 1. The score is now persisted as a series, not a single instant

v1.0 persisted one trust score per station at the window end, so
`/v1/trust/{id}?series=true` returned a single point. A load now scores each
station at a fixed **daily cadence** across the ingest window (config
`trust_weights.yaml → scoring`: `cadence_hours: 24`, `max_points: 120`), anchored
on the most recent reading and stepped backwards to the first, capped at
`max_points` keeping the most recent. Each point is fully explained (components +
reason codes) like any other score. The trailing window of each component still
governs how much history each individual point sees, so early points (near the
start of the window) legitimately see less history.

Cost: one `compute_trust` per station per day. A 30-day, 16-station real load is
~480 scorings; the `max_points` cap bounds a longer load.

### 2. The engineering-judgement formulas are now pinned by invariant tests

The v1 weights are elicited, not fitted, and the component formulas are judgement
calls (v1.0 said so). They are now protected by `tests/unit/test_trust_invariants.py`,
which asserts the *intended shape* rather than the exact constants, so a later
tweak that violates the intent fails loudly:

- **HealthConf** strictly decreases as defect load rises; `severity_weights` are
  strictly ordered critical > high > medium > low > info.
- **SeverityVsThreshold** is 1.0 when clean and rises with a worse active defect.
- **PhysicalPlausibility** is 1.0 comfortably inside bounds, softens in `[0,1)` as
  a reading crowds the upper ceiling, and is 0 at or beyond a bound.
- **Trust** equals the weighted sum of its component contributions, clamped to
  `[0,1]` — the formula cannot drift from `Σ value·weight`.
- **scoring_instants** are ascending, anchored on the last reading, and honour the
  cadence and the `max_points` cap.

These are contracts on behaviour, not a substitute for calibration. The weights
still need a domain-expert sign-off and, eventually, a logistic refit against
labelled events (§7.8) — see the escalation in the phase-2 flag-review report.

### 3. Station coordinates now populate the trust context's geography

The Green Sentinel `Location` column (verified real format `"<site> (lat, lon)"`)
is now parsed into `stations.name`/`lat`/`lon`, and the PostGIS `geom` point is a
STORED generated column derived from them. This does not change any v1 score
(CrossSensorConsistency still uses all peers sharing a parameter), but it lays the
real geography the phase-4 wind-conditioned graph will need for true *nearest*-peer
selection. `zone_type` has **no source** in the export and remains null pending a
curated station→zone mapping (flag-review escalation).

## Unchanged from v1.0

The score `Trust(s,t) = w1·HealthConf + w2·(1−ImputationUncertainty) +
w3·CrossSensorConsistency + w4·PhysicalPlausibility`, the weights (0.35 / 0.15 /
0.20 / 0.30), the ImputationUncertainty placeholder, the reason codes T00–T05, the
Risk formula with its stubbed-and-flagged PopulationExposure, and the
graceful-degradation guarantee are all as described in v1.0. Read v1.0 for those;
this file only records the deltas above.
