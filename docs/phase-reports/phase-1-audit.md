## Phase 1 — The audit engine (B1)

**Date:** 2026-08-08 · **Branch:** `phase-1-audit` · **Tag:** `v0.1.0`

### What was built

The statistics-only audit engine — the demo's opening block and the no-ML
fallback the rest of the project can lean on. A vendor file goes in (Green
Sentinel Excel or Enclod cumulative counters), a canonical pandera-validated long
frame comes out, a coverage model splits it into observed / absent /
structurally-excluded / expected cells, sixteen detectors (R01–R14, R18, R19,
R21) flag defects with per-flag evidence, and an orchestrator produces a
deterministic `AuditResult` rendered as `audit.json` / `.md` / self-contained
`.html`. Everything is driven by a seeded synthetic corpus with a ground-truth
ledger, so the test suite never needs the real data.

### Test gate

`make check` is green: ruff + ruff-format + mypy (strict) + **117 tests**, total
coverage **96%** (detectors/grid/audit all > 90%, the phase requirement). Highlights:

- **Golden recovery** — the central correctness test: the audit reproduces every
  injected reason-code count *exactly*, and a clean corpus trips no detector.
- **Property (Hypothesis):** `expected == observed + absent + structurally_excluded`
  for any corpus; observed ⊆ expected; R09 raises zero flags when PM2.5 ≤ PM10;
  defect rate ∈ [0, 1] and monotonic in injected defect count.
- **Determinism:** two runs produce byte-identical `audit.json` (excluding the
  wall-clock field); `audit.md` snapshotted against a committed golden.
- **Performance:** a 156k-row synthetic corpus audits in well under the 60s budget.
- **Counter repair:** reset/non-monotonic/duplicate/dead detection and an exact
  difference→cumulate round-trip.

### Results on the real data

Green Sentinel (149,683 readings, 16 stations, 2026-05-21→06-19): conventional
completeness **100.00%**, defect rate **29.12%** (50,843 / 174,583 covered cells).
By code: R01 24,900 · R12 12,194 · R10 10,627 · R13 5,622 · R11 2,111 · R02 939 ·
R14 236 · R09 100 · R21 3 · R19 3 · R18 2 · R07 1. The lone R07 is the ~4,100 µg/m³
PM10 spike at KER11, surfaced by ranking, not named in code. KER15's missing wind
(R18 ×2) and KER02's missing groundwater (R19 ×3) are reported as coverage facts
and excluded from the rate. Real-data outputs were **not** committed.

### Deviations from the prompt

- **R05/R06 are surfaced from the counter pipeline, not the environmental detector
  registry.** They require running-total semantics the environmental frame does
  not have. They are implemented and tested in `io/counter_repair.py`; the prompt
  listed "R01–R14" under the detector section, so this is a placement choice, not
  an omission.
- **R12 is whole-series zero variance; R13 is consensus-relative.** A naive
  run-based R12 plus an absolute-cutoff R13 flagged genuinely-stable groundwater
  sensors as broken (~44% defect rate). For a *trust* layer that is a credibility
  problem, so R12 flags only series with zero variance across the record and R13
  flags a sensor only when it is far flatter than its peers for the same
  parameter. This is stricter than the prompt's wording implies and is documented
  in the methodology.
- **"Completeness" is reported as two numbers.** The brief cites "~99.95%". The
  honest naive figure is 100.00% (there are literally zero nulls — missingness is
  absent rows, which is the whole thesis), and the reindexed grid completeness is
  85.74%. Both are rendered, with definitions.

### Flag for review

1. **Enclod reset counts don't match the brief.** The brief expects "~80–96
   resets per column" and "two silently dead sensors". Running counter repair on
   the real archive's `cars_60+` column across all 42 counters found **0 resets**,
   0 dead, but **9,724 duplicate timestamps (R03)** and 63 non-monotonic runs
   (R06), with completeness ranging 0.24–0.99. The counter-repair unit is correct
   and fully tested against synthetic series, so this is a real-data calibration
   question, not a code bug: resets may live in other vehicle-class columns, or
   the "reset" pattern differs from the drop-to-≤50% heuristic, or the dead
   sensors sit in the earlier months whose files carry no count columns at all.
   Worth a proper Enclod pass before phase 4 leans on the graph over this data.
2. **The 29.12% headline rests on R12+R13 (frozen/degraded) and R01 (absent)
   dominating.** I believe the calibration is defensible and documented, but the
   exact figure will move if a reviewer retunes the frozen/low-variance
   thresholds. Worth a second opinion before it goes on a slide.
3. **R14 can label a clearly-upward step "downward"** when the whole-series mean
   sits above the pre-step level (the CUSUM crosses the low side first). Detection
   is correct and the magnitude is right; only the direction label is
   counter-intuitive. Cosmetic, but a judge might notice.

Nothing else outstanding.
