# Update 19 — Network map screenshot review: seven fixes, plus HST-GAT hardening

Branch: `update-19-network-map-review-fixes`. Tag: `v1.0.20-update`.

## What was built

A user review of eight Network-map-tab screenshots (station drawer + map
overlays) raised two explicit asks (the parameter sparklines not resizing like
the trust trajectory chart; the station drawer's Acknowledge/Dispatch wired
into the real sign-off flow) plus follow-up questions about the HST-GAT crash
risk, HST-GAT caching for `make demo-real`, and whether the wind arrow's
direction was correct. Investigating each against the real code surfaced five
more genuine, previously-unreported bugs, all fixed in this pass.

### 1. Parameter sparklines didn't resize with the drawer (the user's ask)

Both the Trust trajectory chart and the per-parameter sparklines
(`StationDetailPanel.tsx`) render through the same `Sparkline` component,
which has a `fluid` prop built specifically for "the resizable station detail
panel" per its own doc comment. Only the Trust trajectory call site passed it;
the parameter sparkline call site (line 396) didn't, so it stayed pinned at a
fixed 160px while the panel stretched around it.

- Added `fluid` to the parameter sparkline's `<Sparkline>` call.
- Wrapped it in a `min-w-0 flex-1` div (it previously had no flex-basis of its
  own to grow into — `justify-between` just left empty space in the row rather
  than stretching the fixed-width SVG) and gave the label column `shrink-0` so
  it doesn't grow to match.
- Existing test coverage already exercises this row; no behavioural assertion
  needed beyond what type-check/lint/existing render tests already cover.

### 2. Wind speed always read "0" — never fetched at all

`NetworkMap.tsx`'s wind readout only ever requested `WIND_DIRECTION_PARAMETER`.
`WIND_SPEED_PARAMETER` was exported (`stationMarkers.ts`) but never imported or
fetched, so `currentWind`'s speed array was structurally always empty and fell
back to its `0` default — "W 0" wasn't a calm reading, it was a silent
missing-fetch. Masked by the test stub mocking `/v1/readings` by path only
(ignoring query params), so the existing test happened to pass regardless.

### 3. Wind reading capped at "1 station" by construction

The same fetch was also scoped to one hardcoded station
(`markers[0]?.stationId`, the alphabetically-first marker), directly
contradicting the adjacent code comment claiming a network-wide aggregation.
`currentWind` was already written to handle multiple stations correctly
(`stationCount: atLatest.length`); the fetch just never gave it more than one
station's data to aggregate.

Fixed 2 and 3 together:

- `useReadings` gained an explicit opt-in `networkWide` flag (default `false`,
  every existing call site unaffected) so a query can run without a
  `stationId`, since the hook previously disabled itself whenever `stationId`
  was falsy.
- `NetworkMap.tsx` now fires two network-wide requests — one per parameter,
  since the API filters by exactly one `parameter` per call — scoped to a new
  `WIND_LOOKBACK_HOURS` (6h) trailing window anchored on the dataset's own
  anchor (`useWindowState().anchor`), independent of whatever macro time
  window (24h/7d/corpus) the operator has selected elsewhere. The narrow
  window matters: `list_readings` orders ascending by timestamp, so a
  network-wide fetch across the full macro window could truncate at the
  200-row page cap before reaching the newest readings.
- Test harness gained a matching capability: a `RouteMap` GET entry can now be
  a function of the request's query params (mirroring the existing
  function-based `PostHandler` pattern), because production now makes two
  simultaneous requests to the same path with different `parameter` values
  that a single fixed fixture can't tell apart.
- `NetworkMap.test.tsx`'s wind test rewritten to filter its fixture by the
  actual query received, and now asserts `stationCount` directly ("2
  stations") — the previous test couldn't have caught either bug, since the
  path-only stub returned the full fixture (including a speed reading and a
  second station) regardless of what was actually requested.

### 4. The wind arrow pointed backwards

`WindOverlay`'s SVG arrow was drawn at `rotate(directionDegrees + 180)`. The
reported bearing is the direction the wind comes *from* (the same number the
adjacent "W"/"278°" text shows, and what the accessible summary explicitly
says: "Wind from W, 278 degrees") — the vane convention points the arrow
*into* the wind, at that same bearing, not 180° away from it. The +180 made
the arrow show the downwind flow direction instead, silently disagreeing with
the text sitting right next to it. Removed the inversion; the arrow now points
at `directionDegrees` directly, matching the label. New assertion pins the
`<g>` element's `transform` attribute directly (`data-testid="wind-arrow"`
added for this).

### 5. "Last reading N days ago" drifting against a frozen corpus

`formatRelative`'s `now` parameter defaults to real `Date.now()`, and both
call sites (`StationDetailPanel`, `QualityMonitor`) used the default. The
corpus is a fixed historical drop, not a live feed — `lib/windowContext.tsx`
already solves exactly this problem for the time-window selector (anchoring on
the newest reading in the data, not the wall clock, with its own comment
explaining why), but nothing had wired the *freshness display* through the
same anchor. Both call sites now pass `useWindowState().anchor` — the same
anchor Trust and the time-window selector already use — so "last reading N
days ago" stops silently growing every day the demo sits unopened.

### 6. Acknowledge/Dispatch wired into the real sign-off flow (the user's ask)

The station drawer's Acknowledge/Dispatch buttons wrote only to a
browser-local queue (`lib/queue.ts`) with no transport out, captioned
"dispatch requires the human sign-off record that lands in phase 7." Phase 7
has, in fact, already landed — the Alert Centre (`/alerts`) has a real,
sign-off-gated dispatch flow (`POST /v1/decision/signoff` →
`POST /v1/decision/dispatch`, backed by `test_signoff_gate.py`'s static
call-graph proof of standing rule 5) — the station drawer's buttons were just
never connected to it.

- Sign-off/dispatch operate on an *event* (`event_id`), not a station directly
  — events only exist once an audit run has raised one
  (`io/db/loader.py::_insert_events`), never created on demand. The panel now
  calls `useEvents(stationId)`, picks the lowest-`rank` (most notable) event
  if one or more exist, and renders the same `SignoffPanel` the Alert Centre
  uses, with a link to that event in the Alert Centre (`/alerts?event=<id>`,
  the same deep-link param the Alert Centre already reads from the URL) for
  the full risk-factor picture and any other events for the station.
  Multi-event stations say how many exist.
- When a station has no adjudicated event yet, the panel says so plainly and
  links to the Alert Centre instead of showing dead buttons.
- `lib/queue.ts` had no other production caller; deleted along with its unit
  tests, and the two stray doc comments elsewhere in the codebase that
  referenced it as the write path.
- `StationDetailPanel.test.tsx`: the two queue-based tests replaced with three
  covering the new behaviour — no event (shows the Alert Centre link, no
  sign-off panel), one event (signs off and dispatches end-to-end through the
  real mutations, mirroring `AlertCentre.test.tsx`'s existing pattern), and
  several events (picks the top-ranked one, links to the Alert Centre for the
  rest).

### 7. HST-GAT macOS/arm64 crash: hardened beyond the two Makefile targets

Answering "is there a way to solve the documented crash risk": partially — a
real, more robust fix was in scope, though not a full elimination of the
underlying dependency conflict. `docs/updates/u17-evidence-review-fixes.md`
mitigated the `libomp.dylib` collision (torch and scikit-learn each load
their own copy; the two colliding inside `run_in_threadpool`'s worker thread
SIGSEGVs the process) with `OMP_NUM_THREADS=1` prefixed onto the `make api`
and `api-bg` Makefile targets only. That left every other way of starting the
API unprotected: the plain `uvicorn` command in `docs/api/README.md`, the
Docker image (believed safe because Debian's `libgomp` is a different
runtime, but never verified), and any IDE run configuration.

`provenance/api/app.py` now sets `OMP_NUM_THREADS=1` (via `os.environ.setdefault`)
as the first statement in the module, before any router import can pull torch
in transitively — so every way of starting the API is protected, not just the
two Makefile targets (whose env var is now a harmless second layer).
Deliberately scoped to this one module rather than `provenance/__init__.py`:
CLI training commands and the pytest suite still want their threads, and only
importing the API app needs the fix. Required an `E402` per-file ignore in
`pyproject.toml` (a statement necessarily precedes the router imports) with
the same rationale recorded there. Verified directly: importing
`provenance.api.app` with `OMP_NUM_THREADS` explicitly unset beforehand shows
it set to `1` immediately after import.

### 8. HST-GAT training is now cached and auto-loaded by `make demo-real`

Answering "can the trained model load automatically on `make demo-real`":
yes. `demo-real-hstgat` was deliberately kept a separate, always-slow
(~4 min) target so re-running `demo-real` to reset state wouldn't pay that
cost just to look at the map again — but that also meant a *first-time* run
never got the Attention overlay without a second, easy-to-forget manual step.

- `prov models train-hstgat` gained `--skip-if-cached`: it computes the
  current data drop's content checksum (the same one that names the artefact
  file, `hst-gat-v1-<checksum8>.pt`), and if a valid, card-verified artefact
  already exists for that *exact* checksum, it prints a message and skips
  training entirely rather than retraining. Any mismatch (different drop,
  corrupted artefact, missing card) falls through to training as normal.
- `make demo-real` now runs `prov models train-hstgat --source data/raw
  --target PM10 --skip-if-cached` automatically after the other model
  training steps. First run against a drop trains it once; every later
  `demo-real` re-run against the same drop reuses the cached artefact instead
  of retraining. `make demo-real-hstgat` is unchanged (always retrains) — for
  a deliberate refresh, e.g. after a config or code change the checksum
  wouldn't catch.
- New CLI integration test (`test_models_cli.py`): trains once against a tiny
  synthetic drop, confirms a second `--skip-if-cached` run reuses the artefact
  untouched (same file, same mtime, "already cached" in the output, no
  retrain), and confirms a third run without the flag retrains as before.

### 9. `docs/api/README.md`'s PopulationExposure example read as permanent

The worked curl example's `population_exposure_stubbed: true` note is real —
it's what the corpus with no GTFS bundle produces — but the doc presented it
without qualifying that a bundle would produce a different, real answer,
reading as if the stub were unconditional. Added one clarifying paragraph
after the example.

## Test gate

**Frontend** (`pnpm test:coverage`): 291 passed (25 files). `pnpm lint` /
`pnpm typecheck` clean.

**Backend** (`make check`): 692 passed, 2 deselected (+3 for the new
`test_models_train_hstgat_skip_if_cached_reuses_matching_artefact`). Coverage
90.96% (gate 88%). `ruff check .` and `mypy` (148 source files) both clean.

## Deviations from the prompt

- The user asked two explicit questions ("is there a way to solve the crash
  risk", "is it possible to cache the training result") rather than
  prescribing an exact fix; item 7's fix is a real hardening, not a full
  elimination of the underlying `libomp` duplicate-runtime conflict — see
  "Flag for review" below for what's still open.
- Five additional bugs (2, 3, 4, 5, 9) were found investigating the two
  explicit asks and the crash/caching questions, not requested directly; the
  user's plan message asked for "these updates" (its own list plus identified
  bugs), so they're included here rather than deferred.

## Flag for review

- **The API's live model discovery still has no staleness check against the
  currently-loaded data.** `store.latest_stem()` (used by
  `GET /v1/graph/attention`) picks the newest-*mtime* `hst-gat-*.pt` file in
  the artefacts directory, not the one matching the checksum of whatever data
  is currently loaded. In the common case this update targets — the same real
  drop, re-training or reusing across repeated `demo-real` runs — this never
  bites, since there's only ever one drop in play. It would bite if the
  artefacts directory ever accumulated models from two *different* real
  drops: the API could silently serve attention weights trained on the wrong
  one, with no error or stale-data indication. Fixing this properly needs the
  live API to know the current DB's own data checksum, which it doesn't
  compute today — judged out of scope for this pass; flagging rather than
  quietly leaving it undocumented.
- `infra/docker/api.Dockerfile` still isn't given the `OMP_NUM_THREADS`
  treatment (Debian's `libgomp` is believed unaffected, per u17), but since
  the fix now lives in `app.py` itself, the Docker image is already covered
  regardless — this note from u17 can probably be considered resolved rather
  than still open, but is repeated here since it was explicitly asked about
  again this session.
