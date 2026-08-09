# Model card - Propagation adjudicator v1

**Type:** Analytic (physics-prior) adjudicator. **No neural network, no training
run.** The learned graph model (HST-GAT) is phase 6; this card is for the
deterministic, analytic B3 adjudicator that ships in phase 4.

**Version:** v1 · **Date:** 2026-08-09 · **Config:** `config/graph.yaml`
(`status: provisional`).

## What it does

Given a candidate event — a rise at station *i* the audit flagged as notable — the
adjudicator decides whether the rest of the network corroborates it the way a real,
wind-borne plume would, and returns one of three verdicts with a full evidence
bundle:

- **GENUINE_EVENT** — downwind neighbours show the expected attenuated, delayed rise.
- **LIKELY_FAULT** — the rise is isolated; downwind neighbours that should have seen
  it stayed flat (reason code R17, "contradicts N connected neighbours").
- **AMBIGUOUS** — partial corroboration, or too few downwind neighbours to judge.
  A **first-class, designed** outcome that routes to human review (reason code R23);
  never a forced binary, and never presented as a confident call.

## Inputs

- Canonical readings frame (the parameter under test, plus `Wind_Direction` /
  `Wind_Speed` when present).
- Station coordinates (real, parsed from the Green Sentinel `Location` column, or
  the fixture sidecar — never invented).
- The wind field at the event hour, station-local where measured and otherwise the
  city-level HungaroMet circular mean, with provenance tracked per edge.
- `config/graph.yaml`: the edge-weight and adjudicator parameters.

## Assumptions and method

- The wind-conditioned edge is a **plume approximation, not a dispersion model**
  (ADR 0007). Downwind alignment, distance decay, and a saturating speed response;
  geometry on a sphere.
- Expected arrival delay is `distance / along-bearing wind speed` (floored);
  expected magnitude is the event excess times the same distance decay as the edge.
- **Cadence.** Readings are hourly and a plume often crosses to a near neighbour in
  under an hour. Rather than interpolate a sub-hourly value we never measured, the
  comparison is **widened to the data cadence**: a neighbour's reading in the hour
  spanning the [15, 60] min horizon is the corroboration sample. The analytic
  sub-hourly delay is still reported in the bundle for a future higher-cadence feed.
- Corroboration is the edge-weighted share of downwind neighbours whose actual rise
  meets the expected attenuated rise within a generous (±50%) band; the verdict is a
  thresholding of that match score plus a minimum-neighbour guard.

## What is NOT reported, and why

**No headline accuracy figure is reported for this method** (standing rule 4, §16
critique 2). There are far too few real corroborated events in a 30-day, ~18-station
corpus to compute a precision/recall/accuracy number that describes anything but the
synthetic injection process used to test it. Reporting one would be a lie of exactly
the kind this product exists to catch. Instead the adjudicator returns **per-case
evidence** — the wind vector, the downwind neighbours and their weights, expected vs
actual series, the match score, and the covariate state — so a human can re-run the
judgement by eye. Calibrated intervals arrive with conformal prediction in phase 6.

## Covariates (stubbed, and said so)

- **Traffic** — `unavailable`. The Enclod counter schema is unconfirmed (ADR 0003);
  the traffic covariate lands once the columns are read.
- **Weather** — `wind-only`. Boundary-layer height and full deweathering (the R20
  meteo-artefact test) are phase 5.

These are named and explained in every bundle rather than silently omitted, so "no
explanation found" is never mistaken for "explanation ruled out".

## Known failure modes

- **No/low wind at the event hour** → AMBIGUOUS (routed to review). Propagation
  cannot be assessed in a calm; the honest answer is "review", not a guess.
- **Too few downwind neighbours carrying the parameter** → AMBIGUOUS. A sparse
  network or a rare parameter can leave nothing to corroborate against.
- **Synthetic-provisional auxiliary topology.** Traffic-counter and bus-corridor
  nodes are placeholders over the station envelope until Enclod/GTFS are confirmed;
  they give the graph its shape but do not yet inform the verdict.
- **A coincident, independent rise** at a downwind neighbour can read as
  corroboration. The generous tolerance band trades false faults for the occasional
  over-corroboration; with more real events this band should be calibrated, not
  widened by feel.
- **Provisional parameters.** Every figure in `config/graph.yaml` is a modelling
  choice, not a calibrated value. The verdict is only as good as those defaults, and
  the characterization test (`tests/fixtures/graph/centrepiece_adjudication.json`)
  exists so any change to them that moves the demo's centrepiece verdict fails CI.

## Determinism

The verdict is a pure function of `(event, geometry, wind at the event hour,
readings, config)`. Two runs over the same inputs produce byte-identical bundles.
