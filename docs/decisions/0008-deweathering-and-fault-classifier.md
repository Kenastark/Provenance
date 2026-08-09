# 0008 - Deweathering residuals, a rule-first fault classifier, and no headline accuracy

**Status:** Accepted (2026-08-09)

## Context

Phase 5 adds the two supervised pieces of the system — deweathering (B2) and the
fault classifier (§7.3) — plus the explainability layer. Three design choices here
are expensive to reverse because everything downstream (anomaly detection, the trust
score, the demo narrative, the model cards) is built on top of them, and because two
of them are as much *ethical* commitments as technical ones.

1. **What feeds anomaly detection — the raw value or the residual?** A raw pollutant
   reading conflates the source and the weather. Comparing raw values across a calm
   night and a windy afternoon flags the weather, not the sensor.
2. **How do a deterministic rule and a learned model share authority?** Both can fire
   on the same reading. If the model can overrule a physics violation, a confident
   wrong model becomes a safety problem.
3. **What single number, if any, describes the fault classifier?** With this few real
   corroborated faults, any headline accuracy describes the synthetic injection
   process, not the world — and a judge will (rightly) probe it.

## Decision

1. **The residual is the signal.** Each pollutant gets a gradient-boosted regressor
   that predicts the reading from meteorology and time alone; `residual = actual −
   predicted` is what anomaly detection sees. The regressors are trained
   forward-chaining only (time-blocked CV, `models/cv.py`), never random K-fold, and
   held to a **0.15–0.90 R² sanity band** — below it the weather is not captured (the
   residual is just the raw value); above it there is no unexplained signal left for a
   genuine event to surface in. Both bounds are failures with distinct, named causes.
   Residuals are stored with the model version that produced them.

2. **Rules first, model for the subtle rest — and the ordering is enforced, not
   documented.** The deterministic Phase-1 detectors run first and short-circuit: a
   physically-impossible reading, a frozen sensor, a comms gap, a unit mismatch are
   decided by rule and the model never gets a vote. LightGBM only ever chooses among
   the three *subtle* classes (`none`, `calibration_drift`, `meteorological_artefact`)
   the rules cannot see. A test drives an adversarial model that always votes
   `calibration_drift` and asserts a physically-impossible reading still resolves to
   `physically_impossible` — the standing-rule "never let the ML override a
   physical-impossibility flag" is pinned in code.

3. **No headline accuracy figure — ever — for the classifier.** The model card
   reports a per-class confusion matrix, per-signature recall against documented
   floors, and the `meteorological_artefact` precision *separately* (misclassifying a
   real inversion as a fault is the most damaging error the system makes). No single
   accuracy/F1 number is produced or quoted (standing rule 4). The recall floors live
   in `config/models.yaml` and the card, not in the pitch.

Provenance is a first-class property throughout: wind direction is encoded as
`(sin, cos)` (so 359° and 1° are neighbours), the boundary-layer height is a
documented proxy, HungaroMet temperature/precipitation are flagged imputed until the
feed is confirmed, and every SHAP attribution carries the provenance of its feature.

## Consequences

- Anomaly detection, the fault classifier's features, and the dashboard's before/after
  chart all speak in residuals; a change to the deweather model changes what they see,
  which is why residuals are versioned with the model.
- The classifier can be *no better than the rules* on the hard classes by design — its
  value is entirely in the subtle cases, and it cannot cause a physics-violation to be
  downgraded.
- Because we refuse a headline number, evaluation is per-case and interval-based, and
  the synthetic `meteorological_artefact` precision is explicitly not a field claim
  (its labels are derived from the residual, so they are near-separable from the
  features — flagged in the model card and the phase report).
- A model that cannot present its provenance (its card) does not load. Missing
  artefacts degrade to the statistics layer rather than failing (standing rule 6).

## Alternatives considered

- **One end-to-end model that both deweathers and classifies.** Rejected: it would let
  a learned signal override physics, and it would have no honest place to draw the
  rule/model authority line.
- **Reporting accuracy with a caveat.** Rejected: the number gets screenshotted, the
  caveat does not. Not producing it is the only reliable way to not oversell it.
