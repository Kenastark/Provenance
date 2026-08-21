# Update 16 — wire the two stale Evidence-tab cards

Branch: `update-16-wire-evidence-tab`. Tag: `v1.0.17-update`.

## What was built

Two Evidence-tab cards were reported as always reading "Not yet computed", despite
the machinery behind both of them already existing. They turned out to have two
unrelated causes, and were fixed accordingly.

### 1. The graph-attention card — a frontend wiring gap, not a missing backend

`DefectEvidence` (`EvidencePanel.tsx`) rendered a fully static
`<NotYetComputed title="Graph attention over neighbouring stations" arrivesIn="the
HST-GAT attention overlay lands in phase 6" />` block — a leftover from the phase-3
placeholder, dated by `git blame` to before phase 5 or phase 6 existed. It never
called any hook. Meanwhile `GET /v1/graph/attention` and the trained
`hst-gat-v1-8f8efeed.pt` artefact (from update-14's real-drop training) both worked
correctly the entire time — the Network Map's "Learned attention (HST-GAT)" layer
(`useAttentionOverlay()`, wired in update-11) proves it. The Evidence tab just never
called that hook.

- **`GraphAttention`** (new, `EvidencePanel.tsx`): calls `useAttentionOverlay()`,
  filters the returned `relations` to the edges touching the flagged reading's
  `station_id`, sorts by attention weight, and renders them as signed bars
  (mirroring `ShapBars`'s layout) labelled with direction, neighbour station, and
  relation name, under a header naming the model's `target_parameter` and snapshot
  `at` timestamp.
- Degrades honestly at three levels, per standing rule 6: loading → `LoadingState`;
  no artefact trained, or the artefact's target parameter absent from the loaded
  drop → the backend's own `reason` string (not a hardcoded one); artefact present
  but no edge happens to touch this specific station → a graph-topology sentence,
  explicitly distinguished from "not yet computed" so an operator doesn't retrain
  looking for something that was never going to appear.
- Replaces the card in place in `DefectEvidence`'s render order (after
  `ShapAttribution` and `DeweatherChart`, same position as before).
- `States.tsx`'s `NotYetComputed` doc comment updated — it referenced "attention
  (phase 6)" as still-pending, which stopped being true once this landed.

### 2. The CO2 residuals card — a training-config gap, not a wiring bug

Unlike the attention card, `DeweatherChart` was already correctly wired to
`GET /v1/deweather/{station_id}`; the card's fallback fires on the backend's own
`degraded: true`. The actual gap was upstream: `CO2` — a confirmed parameter in
`schema_assumptions.yaml`'s `known_parameters`, and on the real drop the single
most common defect parameter (11,228 rows) — was never in `models.yaml`'s
`deweather.pollutants` list (`[PM10, NO2, O3, CO]`). `train_deweather` trains
exactly the configured list intersected with what the frame carries (standing rule
2); CO2 was never requested, so it was never trained, so no CO2 residual could ever
be stored — no matter how many times the card's own suggested commands
(`prov models train` / `prov models residuals`) were run.

- **`config/models.yaml`**: added `CO2` to `deweather.pollutants` — like the other
  three, its local concentration is combustion/dispersion-linked (boundary layer,
  wind), not a metric that "shouldn't" be deweathered.
- Retrained against the real drop and restored residuals:
  `prov models train --source data/raw` → `prov models residuals --source
  data/raw`. Same data, same checksum, same artefact version strings as before
  (`deweather-v1-8f8efeed`, `fault-v1-c40c8de5`) — confirms determinism (standing
  rule 8): this only added a fifth regressor, it did not perturb the other four.
- Verified end to end against the running stack, not just by inspecting code:
  `GET /v1/deweather/DEB-KER01?parameter=CO2` now returns `degraded: false` with a
  real actual/predicted/residual series; `residuals` table confirmed to carry CO2
  rows for all 16 stations (spot-checked five).

### 3. A stale e2e pinning assertion, caught by actually running the suite

`demo-path.spec.ts`'s "the defect table renders with its evidence" test asserted
`getByTestId("not-yet-computed")).toHaveCount(2)` against the real drop's Evidence
tab. Running it after the fix above failed — not because anything was broken, but
because the assertion itself was pinned to the old, wrong behaviour: the real
drop's default top defect turns out to be `DEB-KER01 · CO2` (an R10 unit-mismatch
flag), which is exactly the card the user's screenshot showed. Before this update
that page always carried exactly 2 "not yet computed" slots (1 hardcoded
attention, always; 1 degraded CO2 deweather card, for this specific defect) — now
it carries 0, because both are wired to real data and both resolve for this
station. Updated the assertion to `toHaveCount(0, { timeout: 30_000 })`: 0 because
that is now correct (confirmed independently — `DEB-KER01` has 48 attention edges
in the live overlay and real CO2 residuals), and 30s instead of the file's default
15s because the very first run of this test timed out mid-flight with the
attention card still showing "Loading the attention overlay…" — a real
network+CPU-bound call (`network_frame` read plus the HST-GAT forward pass) racing
a tight assertion window, not a logic error; the immediate re-run resolved in
2.0s. Re-ran green.

## The real-drop R² band: a pre-existing finding, surfaced but not fixed here

Retraining printed the held-out CV R² for all five pollutants on the real drop:

```
Deweather v1-8f8efeed: CO R²=-0.15, CO2 R²=0.26, NO2 R²=0.11, O3 R²=0.38, PM10 R²=-1.96
```

The configured sanity band is `[0.15, 0.90]`. **CO2 (0.26) and O3 (0.38) sit inside
it; CO (-0.15), NO2 (0.11), and PM10 (-1.96) do not** — all three below the floor,
meaning the deweather model is not capturing meteorology for them on the real
drop, so their stored "residual" is close to just the raw value. This is not new
behaviour caused by this update — `train_deweather` never enforced the band at
training time (it is a reporting gate, not a `raise`), these four pollutants were
already trained and their residuals already stored under this exact model version
before this update touched anything, and `test_r2_band_per_pollutant`
(`tests/unit/test_deweather.py`) only ever exercises the synthetic `weather_corpus`
fixture, per standing rule 7 (tests never require the real dataset) — so nothing in
CI has ever run this check against real data. This update's only connection to it
is incidental: retraining to add CO2 is what printed the numbers where they could
be seen. Flagged below; out of scope to chase here.

## Test gate

**Frontend** (`pnpm test:coverage`): 287 passed (25 files, net +1 — one stale test
replaced by two: one for the "not trained" reason path, one for the populated
attention-edges path). Coverage 94.78% lines / 84.99% branches / 84.77% functions
(gate 80%). `pnpm lint` and `pnpm typecheck` clean.

**Backend** (`make check`: ruff, ruff format, mypy strict, pytest, contract-drift
check): `683 passed, 2 deselected, 66 warnings in 351.76s`. `Required test coverage
of 88% reached. Total coverage: 90.59%.` `gen_frontend_contract.py --check`:
current. `pnpm gen:types` against the live schema: no diff — this update added no
new endpoint and changed no response shape, only a YAML config value plus two
frontend components consuming an endpoint that already existed, so no contract
regeneration was expected or needed.

**e2e** (`pnpm exec playwright test demo-path.spec.ts accessibility.spec.ts
--project=chromium`, real API + real 16-station drop already loaded, chromium
only — not the full cross-browser/visual gate, matched to this change's scope):
first run 38/39 passed, 1 failed on a stale pinned assertion (see "A stale e2e
pinning assertion" above); fixed, re-ran the single test green (2.0s). Full
targeted set re-run clean after the fix, including both `evidence` a11y checks
(dark/light) and the "no unrendered template reaches an operator" `/evidence`
check.

No visual baselines regenerated: the Evidence tab (`/evidence`) is not currently
covered by `e2e/visual.spec.ts` (checked — no `evidence` baseline exists in
either the darwin or Linux baseline sets), so there is nothing to re-capture.

## Deviations from the prompt

- The user was asked, and chose, to fix the CO2 gap by retraining rather than by
  only rewording the card's fallback message — the larger of the two options
  offered, because CO2's R² landed inside the band and it is the corpus's most
  common defect parameter, so the gap looked like an oversight worth closing
  rather than a deliberate exclusion.
- Branch/tag numbering: `update-16` and `v1.0.17-update` matched the next free
  slot on the first try — checked against `git tag` and `docs/updates/` before
  writing this report, per [[update-numbering-drift]]. No collision to resolve.

## Flag for review

- **The real-drop R² band failure for CO, NO2, and PM10** (above) is the main
  item. It predates this update and nothing here changed it, but it was only
  surfaced now because retraining printed the per-pollutant numbers. Two honest
  readings are possible: either the feature set (`temperature`/`precipitation`
  imputed constant, `boundary_layer_proxy` a proxy index, `traffic_flow` imputed
  constant — see the model card's Features table) is too weak to explain weather
  for these three on the real network, or the real network's variance in these
  three is genuinely not weather-driven at the hourly resolution this model
  works at. Either way, a human should decide whether this needs a dedicated
  model-quality pass, and whether `test_r2_band_per_pollutant` should grow a
  real-drop variant (carefully — standing rule 7 says tests must not *require*
  the real dataset, so any such test would need to skip gracefully when
  `data/raw` is absent, the way `check-real-drop` does for `make`).
- Model-card commentary: CO2's `mask_fraction`-equivalent framing doesn't exist
  for deweather (that is HST-GAT-specific), so no comparable card language needed
  updating there.
