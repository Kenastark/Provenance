# Audit methodology, v1.1 — step-change localisation

**Supersedes:** `docs/audit-methodology-v1.0.md`.

**What changed:** one detector — R14 STEP_CHANGE — in how it reports *where* and
*how large* a shift was. Detection is unchanged; every other detector, threshold,
and the defect-rate definition are exactly as v1.0 states them.

## Why this revision exists

v1.0 ran a tabular CUSUM over the standardised series and, on the first crossing of
the decision interval, reported that instant as the step and `|value − series mean|`
as its magnitude, plus a `direction` string taken from which arm crossed.

All three of those are wrong on the shape of series R14 exists to catch.

Standardising against the **whole-series** mean means that on a stepped series the
pre-shift half is itself a sustained deviation from that mean. So the arm that
crosses first is usually the one describing the *stable* period, and it crosses
while still inside it. Concretely, on the synthetic corpus — which injects a known
**+15.0 µg/m³ step into NO@STA-02 at hour 168** — v1.0 reported:

| | v1.0 | v1.1 | injected truth |
|---|---|---|---|
| Timestamp | `2026-05-01T11:00` (hour 11) | `2026-05-08T00:00` (hour 168) | hour 168 |
| Magnitude | 6.798 | 15.0 | 15.0 |
| Direction | `"downward"` | *(field removed)* | upward |

The flag *count* was right, which is why the ledger recovery test passed: it
asserted one R14 and got one R14. Everything about that one R14 was wrong.

## The v1.1 definition

Detection and localisation are now separate steps, which is standard practice:

1. **Detect** — the tabular CUSUM, unchanged: `k = 0.5σ`, `h = 5σ` (Montgomery),
   in-control ARL ≈ 465. It answers *did the level shift?* and nothing else.
   Physically impossible readings (R07/R08) and detection-floor values (R11) are
   still excluded from the baseline, as in v1.0.
2. **Locate** — once the CUSUM signals, the changepoint is the split that maximises
   the difference of means either side of it: the standard single-changepoint
   estimator, computed in O(n) from a cumulative sum.

The evidence dict now carries:

| Field | Meaning |
|---|---|
| `signed_magnitude` | `level_after − level_before`; sign *is* the direction |
| `magnitude` | `abs(signed_magnitude)`, used by the operator sentence |
| `level_before`, `level_after` | the two levels, so the number can be checked |
| `baseline_mean` | retained for continuity |

`direction` is **removed**, not corrected. A label derived from which CUSUM arm
crossed first is answering a different question from "which way did the series go";
a signed difference between two measured levels cannot contradict itself, so the
ambiguity is designed out rather than patched.

## Effect on reported numbers

None on any count. R14 fires on the same series, the same number of times: the
defect rate, the by-code breakdown, and the ledger recovery are all unchanged. Only
the timestamp and magnitude *within* each R14 flag change — from wrong to right.

The golden `audit.md` snapshot was regenerated for exactly one line, and the
recovery test now asserts the injected step's size and instant, not just its count.
A count-only assertion could not see this class of error, and did not.

## Everything else in v1.0 still stands

The pipeline, the canonical frame, the coverage model's four separately-reported
quantities, the single defect-rate definition, every threshold and its cited basis,
and the real-data results (149,683 readings, 100.00% conventional completeness,
29.12% defect rate) are unchanged and are still described correctly by v1.0.
