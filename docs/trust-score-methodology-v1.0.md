# Trust Score methodology — v1.0 (statistics-only)

**Status:** Current. Supersedes nothing (first version).
**Scope:** The phase-2 Trust Score. No machine learning; this is the deterministic
floor the whole product degrades to (standing rule 6).

## The score

Per the blueprint §7.8:

```
Trust(s,t) = w1·HealthConf
           + w2·(1 − ImputationUncertainty)
           + w3·CrossSensorConsistency
           + w4·PhysicalPlausibility
```

computed for a station `s` at an instant `t` over a trailing window. The result is
clamped to `[0, 1]`. Every component, its weight, and its contribution are returned
alongside the number, together with at least one reason code — a `TrustScore`
cannot be constructed without them (`trust/score.py`), which is the value-object
half of standing rule 9.

Weights live in `trust/config/trust_weights.yaml` and are **elicited, not fitted**:
domain-expert defaults pending a logistic refit once labelled events exist (§7.8).
The file says so; nothing hides that provenance. v1 weights:

| Component               | Weight | Why this weight |
|-------------------------|:------:|-----------------|
| HealthConf              | 0.35   | Rests on deterministic, defensible active-defect signal |
| ImputationCertainty     | 0.15   | `1 − ImputationUncertainty`; a placeholder term, down-weighted |
| CrossSensorConsistency  | 0.20   | Agreement with neighbours; robust but noisier |
| PhysicalPlausibility    | 0.30   | Rests on the physical bounds — the strongest "is this real?" signal |

## The components

**HealthConf** — `exp(-load / scale)`, where `load` is the severity-weighted count
of defect-counting flags on the station within the trailing window (severity
weights and `scale=3.0` in config). Clean → 1.0. Because a frozen sensor (R12)
flags every hour, a frozen series drives `load` high and HealthConf toward 0, which
is what makes a frozen station score below 0.5.

**ImputationUncertainty** — an **explicit placeholder**. There is no imputation
model in v1. The term is the fraction of the station's covered cells absent in the
window, partially relieved where neighbours still cover the same parameter. It is
reported as `1 − uncertainty`, always with `is_placeholder=true`, and it emits
reason code `T02` (with a note) whenever it actually bites. It must never be
mistaken for a calibrated confidence.

**CrossSensorConsistency** — the mean Spearman rank correlation against the k
nearest peers sharing each parameter, over the window, mapped from `[-1,1]` to
`[0,1]` and averaged across the station's parameters. Rank correlation is robust to
the scale differences between stations. A constant (frozen) target series cannot
track its neighbours and scores 0 for that parameter (`T03`); where fewer than
`min_peers` comparable neighbours exist, consistency is *unavailable* — a neutral
0.5 with `T05`, never a punitive 0.

**PhysicalPlausibility** — the worst-case (minimum) plausibility over the station's
readings in the window: 0 for any reading outside its physical bounds or violating
the PM2.5 ≤ PM10 constraint, softening below 1 only as a value crowds the upper
(dangerous) ceiling. A single physical impossibility is enough to make a station's
data untrustworthy (`T04`).

## Risk

```
Risk = Trust × SeverityVsThreshold × PopulationExposure
```

`SeverityVsThreshold` scales with the worst active defect severity in the window
(1.0 when clean). `PopulationExposure` is **stubbed at 1.0 until GTFS ridership
lands** (phase 7); the response carries `population_exposure_stubbed=true` and a
note, so it is never silently defaulted.

## Reason codes

Trust codes `T00`–`T05` (registry, category `trust`, none count toward the defect
rate) explain the score: `T00` nominal, `T01` low health, `T02` imputation
placeholder, `T03` cross-sensor disagreement, `T04` implausible value, `T05`
insufficient neighbours. A clean, well-covered, well-correlated station reports
`T00`; anything that pulls the score down reports why.

## What v1 deliberately does not do

- No headline accuracy figure — there is nothing to score against yet.
- No imputation model (the T02 placeholder stands in).
- No graph/wind conditioning (phase 4) and no deweathering (phase 5); when those
  models are missing the score still computes from statistics alone and says
  `degraded` where a caller signals a missing artefact (standing rule 6).

## Calibration expectations for v1.1+

Once labelled events exist, refit the weights by logistic regression against the
labels (§7.8), replace the ImputationUncertainty placeholder with the phase-5
model, and fold the phase-4 spatial-consistency signal in as a fifth term. Each of
those is a new version of this document, not an edit to this one (standing rule 10).
