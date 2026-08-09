## Phase 4 - Wind-conditioned graph and propagation adjudicator

Date: 2026-08-09 · Branch: `phase-4-graph` · Tag: `v0.4.0`

### What was built

The heterogeneous graph and the analytic B3 adjudicator — no neural network, that
is phase 6. A `GraphSnapshot` value object carries node tables (EnvStation,
TrafficCounter, BusStop aggregated to bounded corridors, WeatherNode) and the five
edge types at one timestamp, over numpy/pandas, as the deliberate seam phase 6 will
back with PyG. Wind-conditioned edge weights are a documented plume approximation
(ADR 0007) with geodesic bearings, correct 0/360 wraparound, a saturating speed
response, distance decay, and a city-level wind fallback for stations without a
sensor. `validate_event()` adjudicates a candidate event to GENUINE_EVENT /
LIKELY_FAULT / AMBIGUOUS with a full evidence bundle; AMBIGUOUS is first-class and
routes to review. A replay harness ranks the corpus's events and writes bundles;
the dashboard gained a wind-edge map layer, per-verdict colouring, and an event
detail view (expected vs actual, verdict + confidence, neighbours, covariate stubs).

### Test gate

All green.

- **Backend:** `ruff check`, `ruff format --check`, `mypy --strict`, and the full
  `pytest` suite pass — **368 passed**, total coverage **92.78%** (gate 88%). The
  new `graph/` modules are covered 88–100%.
- **Analytic geometry:** perpendicular wind → near-zero weight (~2% of aligned),
  aligned → maximum, a 180° reversal swaps which of a pair is downwind; angular
  wraparound (359° vs 1° = 2°); weight monotone in distance and in angular offset;
  zero wind → finite, NaN-free degenerate graph. Property tests (hypothesis) sweep
  the geometry and wind.
- **Adjudicator:** synthetic corroborated plume → GENUINE; isolated spike → FAULT
  (R17); partial corroboration → AMBIGUOUS (never a forced binary); an AMBIGUOUS
  verdict cannot be constructed as high confidence (value-object invariant).
- **Characterization:** the KER11-analogue corroborated-plume adjudication (verdict,
  match score, neighbour set) is frozen from the run in
  `tests/fixtures/graph/centrepiece_adjudication.json`; any change that moves it
  fails CI.
- **Invariants:** edge weights are a pure function of (geometry, wind at t, config);
  BusStop aggregation is bounded; snapshots are deterministic and NaN/inf-free
  across the corpus. **Performance:** a single-timestep rebuild is ~20 ms (budget
  100 ms).
- **Frontend:** eslint, `tsc`, `vitest` (**188 passed**), and `vite build` all pass;
  the frontend contract (`--check`) and generated `schema.d.ts` are current.

### Deviations from the prompt

- **ADR filename.** The brief asked for `docs/decisions/0004-wind-edges.md`, but
  `0004` was already taken by `0004-api-auth-phase2.md` (phase 2), and ADRs are
  numbered sequentially and never renumbered. It is therefore
  `docs/decisions/0007-wind-edges.md`, with a note at the top explaining the number.
- **The KER11 characterization is a synthetic KER11-analogue.** The real ~4,100
  µg/m³ event lives only in the un-committed Green Sentinel export, and tests must
  never require the real dataset (standing rule 7). So CI freezes a KER11-shaped
  corroborated plume built by `graph/scenarios.py`; the replay CLI adjudicates the
  true event live when pointed at a real drop (`prov graph adjudicate --data ...`),
  with no station or verdict hardcoded anywhere.
- **Adjudicator reason codes.** GENUINE and AMBIGUOUS needed vocabulary the registry
  did not have, so R22 (PLUME_CORROBORATED) and R23 (ADJUDICATION_AMBIGUOUS) were
  added under a new `adjudication` category; the fault case reuses the phase-4
  reserved R17. None count toward the defect rate — the adjudicator is not a
  detector, so the headline number is untouched.
- **`graph` layering guard added.** `tests/architecture/test_layering.py` now
  forbids `graph` from importing `api`/`report`/`models`/`explain`, matching the
  documented pipeline. This is an addition to the guardrail, not a change to
  existing rules.
- The demo corpus and the two auxiliary node types remain **synthetic-provisional**
  (see Flag for review).

### Flag for review

Two things a human should weigh before phase 5/6 builds on them:

1. **The demo corpus carries no wind, so its stored verdicts are all AMBIGUOUS.**
   The synthetic fixture/demo corpus has no `Wind_Direction`/`Wind_Speed`, so
   `prov graph adjudicate-db` over it honestly returns AMBIGUOUS for every event
   (a plume cannot be assessed without wind). That is correct and non-guessing, but
   it means the **dashboard timeline** on `make demo` shows AMBIGUOUS labels, not a
   GENUINE one. The GENUINE centrepiece is shown via `prov graph adjudicate` over the
   committed scenario (or the real drop). If we want the dashboard timeline itself to
   show a GENUINE verdict on stage, the demo corpus needs wind + a propagating plume
   — an opt-in flag on the fixture generator I deliberately did **not** add this
   phase to avoid perturbing the golden ledger. Worth a decision before Checkpoint 4
   capture.
2. **Traffic-counter and bus-corridor nodes are placeholder topology.** Enclod and
   GTFS schemas are still unconfirmed (ADR 0003), so those nodes are placed
   deterministically over the station envelope and marked `synthetic-provisional`.
   They give the graph the right shape and bound the BusStop count, and the traffic
   covariate in the adjudicator is an explicit stub — but nobody should read a real
   traffic or transit signal into the map or the bundle yet.

### Demo checkpoint 4

B1 → B3 runs end to end: `prov graph adjudicate` produces the ranked bundles, the
top one being the corroborated KER11-shaped plume → **GENUINE_EVENT**, the isolated
contrast case → **LIKELY_FAULT**, and a partial case → **AMBIGUOUS** (routed to
review). All three framings exist in code and are frozen, so the B3 narration can be
scripted against the outcome we actually have rather than discovered live.
