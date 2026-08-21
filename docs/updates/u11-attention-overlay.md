# Update 11 — the HST-GAT's attention as a map overlay

Branch: `update-10-attention-overlay`. Tag: `v1.0.12-update`.

Per the working agreement for these update reports: what follows is copy-pasted or
directly quoted from a real command's output, not retyped or rounded by hand beyond
what the tool itself already rounded.

Note on numbering: the prompt asked for branch `update-10-attention-overlay` and tag
`v1.0.11-update`. Both were already taken by the time this work started — `u10-alert-
centre.md` (branch `update-9-alert-centre`) shipped as `v1.0.11-update` earlier the
same day. This report and its tag take the next free slot (`u11`, `v1.0.12-update`);
the branch name is kept exactly as given, since the prior update's own branch/tag
pair (`update-9-alert-centre` → `v1.0.11-update`) already establishes that the branch
number and the doc/tag number are allowed to diverge in this repo.

## Design decision: serve the overlay live from the DB, not a precomputed file

`attention.py`'s tested, product-reachable entry point is `write_overlay_for_drop`,
called by the CLI's `graph adjudicate --learned` to write `attention_overlay.json` to
the adjudications report directory. Two ways to serve that through the API:

1. Read that precomputed JSON file from disk on request.
2. Recompute the overlay live from whatever is currently in the database.

(1) is simpler but ties the map to whenever `--learned` was last run on disk, which
can silently disagree with what the DB (and every other screen) currently shows.
(2) keeps one source of truth — the same DB-backed frame every other endpoint reads —
at the cost of a new `repository.network_frame()` (mirrors `station_frame()` without
the station filter) and a forward pass per request. Went with (2): `GET
/v1/graph/attention` checks `store.latest_stem()` first (a cheap glob, no torch
forward pass) and returns `available: false` immediately when nothing is trained —
which is the common case, since neither `make demo`/`demo-data`/`demo-models` trains
the HST-GAT by default (`make models train-hstgat` is opt-in, matching
[[phase6-demo-framing-learned-path]]). Only when an artefact exists does it read
`repository.network_frame()` + `list_stations()` and run `attention_overlay()` in a
worker thread (`run_in_threadpool`, like the explain endpoint's SHAP path).

## What was built

1. **`GET /v1/graph/attention`** (new `api/routers/graph.py`, public-read). Returns
   `AttentionOverlayOut { available, reason, at, target_parameter, relations }`.
   `available: false` with a reason a human (and the layer toggle's tooltip) can read
   covers two distinct degraded states: no HST-GAT artefact trained at all, and an
   artefact trained whose `target_parameter` is not present in the data currently
   loaded (checked before calling `attention_overlay()`; a `ValueError` from no
   mapped station carrying the parameter is also caught as the same degraded case,
   never a 500). Never an accuracy claim (standing rule 4) — the response is edges
   and their attention weights, nothing else.
2. **`repository.network_frame()`** (`io/db/repository.py`): the whole network's
   readings as one canonical long frame, factored against the existing
   `station_frame()` via a shared `_frame_from_reading_rows()` helper rather than
   duplicating the pandas construction.
3. **Frontend**: `useAttentionOverlay()` (`api/queries.ts`); `resolveMapLayers`
   (`stationMarkers.ts`) gained an `attentionOverlay` layer — same disabled-until-
   the-endpoint-answers shape as `busStop`/`trafficCounter`, except the tooltip is
   the backend's own `reason` string once it has answered, not a generic
   placeholder, since standing rule 6 specifically asks for "the model has not been
   trained" on the toggle itself. `attentionEdgesFromOverlay` (`windEdges.ts`)
   resolves each edge's station ids against the current markers — the same lookup
   the analytic wind edges are drawn from — so an edge naming an unmapped station is
   dropped rather than drawn at the origin, and the two layers can never drift apart
   geometrically. `AttentionEdgeLayer` (`MapOverlays.tsx`) draws dashed lines
   (`strokeDasharray`) on the one interactive colour the palette allows
   (`var(--prov-interactive)`), width and opacity scaled directly by `attention`
   (already a softmax weight in `[0, 1]`, unlike the wind kernel's unbounded weight,
   so no local-maximum renormalisation is needed).
4. **Frontend contract regenerated** (`make web-contract`): `openapi.json`,
   `schema.d.ts` now carry `AttentionOverlayOut`/`AttentionEdgeOut` and the new
   route; `client.ts` gained the `AttentionOverlay` alias and its route-match
   assertion.

## Test gate

- `make check` (ruff, ruff format, mypy strict, pytest, contract-drift check):
  `680 passed, 2 deselected, 52 warnings in 371.21s`. `Required test coverage of 88%
  reached. Total coverage: 90.92%.` New backend coverage: `tests/integration/
  test_graph_attention_api.py` (degrades without an artefact; serves real edges once
  an HST-GAT is trained on a matching drop, station ids and target parameter
  agreeing with the DB) plus a new row in `test_api_auth.py`'s auth matrix
  (`/v1/graph/attention`, public tier).
- `pnpm vitest run`: `276 passed` across `24` test files, including new coverage for
  `attentionEdgesFromOverlay` (`windEdges.test.ts`: resolves ids against markers,
  drops an edge naming an unmapped station, flattens every relation strongest-first,
  empty overlay) and `resolveMapLayers`/`NetworkMap` (`NetworkMap.test.tsx`: toggle
  disabled with the backend's "has not been trained" tooltip by default, enabled and
  drawing dashed `var(--prov-interactive)` edges once the HST-GAT is trained, never
  drawn while the toggle is off even with real data available).
- `pnpm exec tsc --noEmit` and `pnpm exec eslint` on every changed file: clean.
- `make web-contract-check`: green once committed (the Python-side
  `gen_frontend_contract.py --check` passed mid-development; the `git diff
  --exit-code -- schema.d.ts` half of that target only compares the working tree
  against `HEAD`, so it necessarily "fails" on an uncommitted branch — resolved by
  this commit).
- Visual baselines regenerated on both platforms after a genuinely clean
  `docker compose down -v && make up && make demo-data` (the same remedy the
  immediately prior commit, `297db98`, used) with local model artefacts moved aside
  during capture so the pinned state matches a fresh clone (gitignored, never
  present in CI): Linux, in the pinned `mcr.microsoft.com/playwright:v1.62.1-noble`
  container — `12 passed (1.6m)` on capture (only `map-dark`/`map-light` regenerated,
  nothing else), `12 passed (1.7m)` re-verified stable via `make web-visual-check`;
  darwin, locally via `playwright test --project=chromium e2e/visual.spec.ts
  --update-snapshots` — `12 passed (44.6s)`. Only the four `map-*` baselines (both
  themes, both platforms) are committed — see the deviation below re.
  `station-detail-*-darwin`.
- Manually verified against the live demo API: `curl /v1/graph/attention` returns
  `{"available": false, "reason": "The HST-GAT has not been trained. Run \`prov
  models train-hstgat\` to enable the learned attention overlay.", "at": null,
  "target_parameter": null, "relations": {}}` against the fresh demo corpus (no
  models trained, matching `make demo-data`'s deliberate no-models state).

## Deviations from the prompt

- Branch/tag/doc numbering: see the note at the top. Not a deviation in substance —
  the branch name is exactly as instructed — only the doc filename (`u11` not `u10`)
  and tag (`v1.0.12-update` not `v1.0.11-update`) shift to the next free slot.
- **`station-detail-{dark,light}-chromium-darwin.png` regenerated during capture but
  reverted**, same call as `u5-map-layers.md` made for the same reason: this update
  touches nothing `StationDetailPanel`/`TrustChip` import, and the *Linux* capture
  (identical backend, identical freshly-loaded DB) reproduced the existing
  station-detail baseline exactly — only darwin diverged. Re-ran `station detail`
  alone without `--update-snapshots` to confirm this is real and reproducible on
  this machine right now (`5571 pixels (ratio 0.02)` different, a vertical content
  shift starting right below "Trust score"), against the baseline as committed on
  `main` — nothing this update touches renders that panel. Reverted both files with
  `git checkout --` rather than committing an unrelated fix; see Flag for review.
- The API-serves-live-from-the-DB design (vs. serving the CLI's precomputed
  `attention_overlay.json`) wasn't specified in the prompt; recorded as a design
  decision above rather than silently picked.

## Flag for review

- **The darwin `station-detail` visual baseline is currently stale against `main`
  itself**, independent of this branch — a pre-existing local-environment drift
  (see the deviation above), not something this update introduced or fixed. Worth
  a dedicated look before it's mistaken for a regression in some future update's
  capture pass.
- `GET /v1/graph/attention` reads every reading in the database on every request
  once a model is trained (`repository.network_frame()`, no filter) — fine for the
  demo's 18-station/60-day corpus, measured comfortably sub-second, but the same
  "no caching, re-reads everything per call" shape `u5-map-layers.md` already
  flagged for the reference-layer endpoints. `staleTime: Infinity` on the frontend
  query keeps this to once per page load; worth a look if the overlay ever needs to
  be genuinely live (a query-param `at` was deliberately not added — out of scope
  here, and the map's other "current" readouts, like `WindOverlay`, are all "latest
  hour" too).
- Neither `make demo`/`demo-data`/`demo-models` trains the HST-GAT, so the shipped
  default state for this whole feature is the disabled toggle — correct per
  standing rule 6 and consistent with [[phase6-demo-framing-learned-path]], but
  worth knowing before the demo: showing the learned overlay on stage needs an
  explicit `prov models train-hstgat` first.
