# Trust Score methodology, v1.1 — bounded health load

**Supersedes:** `docs/trust-score-methodology-v1.0.md`.

**What changed:** one thing — how `HealthConf` measures fault load. The score's
functional form, its four components, and its weights are unchanged from v1.0.
Everything not restated here still holds as written in v1.0.

## Why this revision exists

v1.0 computed

```
load = Σ severity_weight(flag)     for every defect FLAG ROW on the station
HealthConf = exp(-load / 3.0)
```

Detectors flag every defective *cell*. A sensor frozen for a week produces ~168
flag rows; a single impossible reading produces one. So load scaled with window
length and flag volume rather than with how broken the station was, and the
exponential turned that into saturation.

Measured against the real Green Sentinel export, `HealthConf` was:

| | v1.0 | v1.1 |
|---|---|---|
| Range across the 16 stations | 8.7e-25 … 5.8e-88 | 0.468 … 0.793 |
| Stations below 1e-6 | 16 of 16 | 0 of 16 |

At 1e-25 the term is indistinguishable from zero in a weighted sum, so **35% of
the trust score (w1) was contributing nothing at all**, uniformly, for every
station. The score still ranked stations — but on three components, not four,
and nothing in the test suite said so. The v1.0 phase gates (`perfect > 0.95`,
`frozen < 0.5`) are satisfied by a saturated component exactly as well as by a
calibrated one, which is how this shipped.

## The v1.1 definition

```
load = Σ worst_severity(cell) / covered_cells        over defective cells in the window
HealthConf = exp(-load / 0.3)
```

`load` is now the **severity-weighted fraction of the station's cells that are
defective**, so it is bounded by 1.0 (every cell critical) however long the window
is and however many flags fired. A cell counts once at its worst severity however
many codes fired on it — the same discipline the defect rate uses, for the same
reason. Coverage facts (R18/R19) are excluded: a sensor a station never carried is
not a fault.

`decay_scale` moves 3.0 → 0.3 because the unit changed from "flags" to "fraction";
the two numbers are not comparable and the old one has no meaning under the new
definition.

### Anchors

- A sensor frozen across a station's whole record spoils 100% of its cells at high
  severity: `load = 0.7`, `HealthConf = exp(-0.7/0.3) ≈ 0.10`. Such a station also
  scores 0 on CrossSensorConsistency, putting total trust near **0.48** — below the
  0.5 fault threshold in the design tokens, as a wholly frozen station must be.
- A station losing one of thirteen parameters carries `load ≈ 0.054` and scores
  **≈ 0.84**. Twelve good channels are still good; this is the correct answer and
  v1.0 could not express it.

### Why not simply count fault episodes?

An intermediate design counted *episodes* — maximal runs of one code on one series
— instead of flag rows. That fixes the freeze (one fault, not 168) but not the
general case: real stations carry ~40–85 distinct episodes each, mostly scattered
single-hour absences, so load still reached the tens and `HealthConf` still floored
at 1e-4. Measured on the real export it moved the range only to 0.0000 … 0.0271.

Episodes remain the right unit for *explaining* a score and are computed for that
purpose (`detectors/episodes.py`); the component's `detail` reads e.g.
`"31 active fault(s) spoiling 41.6% of readings"`. They are not the right unit for
the arithmetic.

### Complementarity

A lone impossible reading barely moves `HealthConf`, by design: it spoils one cell
out of thousands. `PhysicalPlausibility` already vetoes to 0 on R07/R08/R09, so the
impossible-reading case is covered by the component that exists for it. v1.1 keeps
the two answering different questions — *how much is spoiled* versus *is anything
impossible* — rather than having both answer the first one badly.

## Testing changes

The threshold gates from v1.0 are kept, and a discrimination property is added
alongside them, because those gates cannot see the failure this revision fixes:

- `HealthConf` must **rank** a clean station above a spiked one above a frozen one,
  with the spread staying usable rather than crushed against zero.
- Load must not scale with window length: doubling a freeze's duration spoils the
  same 100% of the station and must score the same.
- A station losing one parameter must stay more trusted than one wholly frozen.

## Status of the weights

Unchanged from v1.0 and still **elicited, not fitted** — `status: elicited` in
`trust_weights.yaml`. The logistic refit against labelled events (§7.8) should be
run against this definition, not v1.0's: fitting weights while w1 is a constant
zero would bake the saturation into the fitted values and make it very hard to
find later.

## Not changed in v1.1

- `Trust = w1·HealthConf + w2·(1−ImputationUncertainty) + w3·CrossSensorConsistency
  + w4·PhysicalPlausibility`, weights 0.35 / 0.15 / 0.20 / 0.30.
- `ImputationUncertainty` remains an explicit, flagged placeholder with no model
  behind it.
- `Risk = Trust × SeverityVsThreshold × PopulationExposure`, with
  `PopulationExposure` stubbed at 1.0 and carried as stubbed, never silently
  defaulted.
- Standing rule 9: a `TrustScore` still cannot be constructed without its component
  breakdown and at least one reason code.
