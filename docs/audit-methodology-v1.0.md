# Audit methodology, v1.0

*Provenance — the statistics-only audit (B1). No machine learning is used in
anything described here.*

This is the document to hand a judge who asks **"how did you get that number?"**
Every threshold below has a physical or statistical justification, and every
figure Provenance reports is computed from the data by a code path you can point
at — nothing is hardcoded (standing rule 1).

## 1. What the audit claims, in one paragraph

A number on a screen looks identical whether it is true or broken. The Green
Sentinel network is, by the conventional measure, perfectly healthy: **149,683
readings, 100.00% of them non-null.** Provenance reindexes every series against
the grid it *should* have produced, checks each reading against physics and
against its own history, and finds that **29.12% of the expected readings are
absent, frozen, mislabelled, censored, or physically impossible.** Each flag
carries the evidence that produced it.

## 2. The pipeline

```
io -> schema -> grid -> detectors -> audit -> report
```

- **io** reads the vendor files (Hungarian-schema Excel for Green Sentinel;
  cumulative CSV counters for Enclod) into one canonical long frame. Field names
  and units are read from the files and validated against
  `config/schema_assumptions.yaml`; drift raises `SchemaDriftError` rather than
  being silently coerced.
- **schema** validates the canonical frame with pandera and attaches a
  deterministic `row_hash`, so two runs over the same input are byte-identical.
- **grid** builds the coverage model (§4).
- **detectors** each flag one reason code as a pure function
  `detect(frame, ctx) -> DefectFrame` (§5).
- **audit** counts defective *cells*, applies the one defect-rate definition, and
  ranks notable events.
- **report** renders `audit.json`, `audit.md`, and a self-contained `audit.html`.

## 3. The canonical frame

One row per observed reading:
`station_id, parameter, timestamp_utc, value, unit, instrument_id (nullable),
source_file, row_hash`. Timestamps are normalised to UTC; the Green Sentinel
export is timezone-naive and is treated as UTC, a decision recorded in the
observed-schema manifest.

## 4. The coverage model — four quantities, kept separate

Conflating these is what inflates the most scrutinised number in the pitch, so
they are computed and reported separately, and an identity ties them together:

| Quantity | Meaning |
|---|---|
| **observed** | readings actually present |
| **absent** | covered ticks with no reading (missingness → R01) |
| **structurally excluded** | ticks for a (station, parameter) the station never carried |
| **expected** | `observed + absent + structurally_excluded` |

This identity is enforced for every generated corpus by a Hypothesis property
test. **Cadence is inferred per series** (air and groundwater tick hourly; noise
ticks daily), so reindexing a daily series against an hourly grid cannot invent
phantom absences.

**Structural absence is inferred from the data, never hardcoded** (standing
rule 3). A station is judged to lack a sensor when a parameter carried by a
majority of the network is entirely absent from that station. This rule recovers
the two documented cases — KER15 carries no wind sensors (R18 ×2), KER02 has no
groundwater source (R19 ×3) — without naming a single station in code. Structural
cells are excluded from **both** the numerator and the denominator of the defect
rate.

## 5. The defect rate — one definition

There is exactly one definition of the defect rate in the codebase
(`grid/defect_rate.py`), and every report renders it beside the number:

> **defect rate = defective covered cells / covered cells**, where a covered cell
> is one (station, parameter, hour) the station actually measures, and a defective
> cell is one on which at least one defect-counting reason code fired. Structural
> absences are excluded from both the numerator and the denominator.

A cell is counted once, however many codes fired on it.

## 6. Detectors, thresholds, and their basis

Coverage codes (R18, R19) do **not** count toward the defect rate. All thresholds
live in `config/thresholds.yaml` with the justification reproduced here.

| Code | Name | What it flags | Threshold & basis |
|---|---|---|---|
| **R01** | ROW_ABSENT | A covered tick with no reading | Reindex each series against its inferred cadence. No threshold. |
| **R02** | COMM_GAP | A run of absent ticks that means an outage | ≥ 6 consecutive hours — beyond routine sample loss. |
| **R03** | DUPLICATE_TIMESTAMP | Two readings for the same (station, param, hour) | Any duplicate. |
| **R04** | TIMESTAMP_OUT_OF_ORDER | A reading stamped before an earlier one | Any inversion in file order. |
| **R05** | COUNTER_RESET | A cumulative counter restarted near zero | Drop to ≤ 50% of the previous total (counter repair). |
| **R06** | COUNTER_NONMONOTONIC | A counter ticked backward without a reset | Any un-explained decrease. |
| **R07** | EXCEEDS_PHYSICAL_MAX | Value above the instrument-plausible ceiling | Per-parameter ceilings, e.g. PM10 > 2000 µg/m³ (extreme Saharan dust tops ~1000–1500; the 4100.7 reading at KER11 trips this). |
| **R08** | BELOW_PHYSICAL_MIN | Value below the physical floor | Per-parameter floors, e.g. humidity < 0%. |
| **R09** | CROSS_PARAM_INVERSION | PM2.5 > PM10 | Definitional: PM2.5 particles are a subset of PM10. Tolerance 0. |
| **R10** | UNIT_INCONSISTENT | Declared unit contradicts the value range | CO2 labelled µg/m³ whose median sits in the ppm range (300–10000); at ambient concentration µg/m³ CO2 would be ~10⁶ larger. |
| **R11** | DETECTION_LIMIT_FLOOR | Left-censored readings pinned at the floor | ≥ 6 consecutive values at the limit (NO floor = 0.7 µg/m³). |
| **R12** | ZERO_VARIANCE | A frozen sensor | A covered series with zero variance across the whole record. |
| **R13** | LOW_VARIANCE_DEGRADED | A sensor abnormally flat *relative to its peers* | Standard deviation < 10% of the network-median std for that parameter (so a uniformly stable parameter does not trip). |
| **R14** | STEP_CHANGE | A sustained level shift | Tabular CUSUM, k = 0.5σ, h = 5σ (Montgomery SPC defaults; in-control ARL ≈ 465). Physically impossible and floor-censored values are excluded from the baseline, as they belong to R07/R08/R11. |
| **R21** | SENSOR_DEAD | A series that stopped and never resumed | Silent for ≥ 72h before the window end (env); a counter that never advances for a week (traffic). |

## 7. Traffic counter repair

The Enclod counters report a running total per vehicle class every 15 minutes.
`io/counter_repair.py` dedupes duplicate timestamps, sorts, differences
reset-aware, reconstructs per-interval counts, and marks dead sensors. Its
`difference`/`cumulate` pair are exact inverses on a clean series — a property the
test suite checks with a round-trip test.

## 8. Determinism and testing

- Everything is seeded; two runs over the same input produce byte-identical
  `audit.json` (excluding the wall-clock `generated_at`).
- The whole suite runs against a **seeded synthetic corpus**, never the real
  export. The corpus injects every reason code a known number of times; the
  golden recovery test asserts the audit reproduces each count **exactly**, and a
  clean corpus trips no detector.
- Coverage on `detectors/`, `grid/`, and `audit/` exceeds 90%.

## 9. Results on the real data (2026-05-21 → 2026-06-19)

Green Sentinel export, 16 land stations:

| | |
|---|---|
| Readings | 149,683 |
| Conventional completeness (non-null) | 100.0000% |
| Grid completeness (observed / covered) | 85.74% |
| **Defect rate** | **29.12%** (50,843 of 174,583 covered cells) |

By code: R01 24,900 · R12 12,194 · R10 10,627 · R13 5,622 · R11 2,111 ·
R02 939 · R14 236 · R09 100 · R21 3 · R19 3 · R18 2 · R07 1.

The single R07 is the ~4,100 µg/m³ PM10 spike at KER11 — the headline notable
event, surfaced by ranking, not by being named in code.

Enclod bundle (42 cumulative counters, 15-minute, ~1.53M rows): counter repair
runs across the archive and finds pervasive duplicate timestamps, occasional
non-monotonic runs, and highly variable completeness (0.24–0.99 across counters).
See the phase-1 report for the open question on reset counts.

---
*Supersedes: nothing (first version). This document is versioned, never edited in
place; a revision is a new `audit-methodology-vX.Y-*.md` that says what it
supersedes.*
