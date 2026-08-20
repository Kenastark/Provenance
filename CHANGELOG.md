# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]
### Added
- `AGENTS.md`: a short pointer at the repo root so agents that look for that
  filename by convention land somewhere useful, without becoming a second copy of
  CLAUDE.md's rules. `tests/architecture/test_agents_md.py` guards its length and
  bans a numbered rules list, so it cannot silently grow into a duplicate that
  drifts out of sync with CLAUDE.md.
- `tests/architecture/test_brand.py`: every `.svg` under `design/logo/` and
  `apps/web/public/` is now parsed with a strict XML parser. This is the guard that
  should have caught the dark-mode lockup shipping as an unparseable file.

### Fixed
- **The dark-mode top-bar lockup did not render at all.** The generator at
  `scripts/gen_reversed_lockup.py` wrote a comment containing `--prov-white`, and a
  double hyphen is illegal inside an XML comment. Browsers parsing SVG-in-`<img>`
  are strict and reject the whole file, so the dashboard's default (dark) theme
  showed a broken image where the lockup belongs; the light theme was unaffected,
  since it uses the unreversed asset. Fixed at the source by rewording the
  generator's note, then regenerating both `design/logo/` and its
  `apps/web/public/` mirror. All sixteen visual baselines had been captured with
  the broken image in place on every dark-theme screen, so the visual-regression
  gate had been blessing the bug rather than catching it.
- **Trust Score: `HealthConf` was a constant zero for every station.** It summed one
  severity weight per defect *flag row*, and detectors flag every defective cell, so
  load scaled with window length and flag volume rather than with how broken a
  station was. Measured on the real export it ranged 8.7e-25 .. 5.8e-88 across all
  sixteen stations - w1 (35% of the score) contributed nothing, uniformly, and no
  test noticed, because the phase gates (`perfect > 0.95`, `frozen < 0.5`) are
  satisfied by saturation exactly as well as by calibration. Load is now the
  severity-weighted **fraction** of a station's cells that are defective, bounded by
  1.0 by construction; `decay_scale` moves 3.0 -> 0.3 with the unit change. The
  real-data range is now 0.468 .. 0.793. See
  `docs/trust-score-methodology-v1.1-bounded-health-load.md`.
- **R14 STEP_CHANGE reported the wrong instant and the wrong size.** Reading the
  changepoint off the CUSUM crossing put it inside the *stable* stretch, because
  standardising against the whole-series mean makes the pre-shift half look like a
  sustained deviation in its own right. On the fixture's known +15.0 step at hour
  168, it reported hour 11 and a magnitude of 6.798, and labelled the rise
  "downward". Detection (CUSUM, unchanged) is now separated from localisation (the
  split maximising the difference of means), and the injected step is recovered
  exactly. The ambiguous `direction` field is removed in favour of
  `signed_magnitude`, `level_before` and `level_after`. No defect count changes. See
  `docs/audit-methodology-v1.1-step-change-localisation.md`.

### Added
- `detectors/episodes.py`: collapses per-cell flags into distinct fault episodes
  (maximal runs of one code on one series, at that series' own cadence). Used to
  explain a trust score in operator terms - "31 active fault(s) spoiling 41.6% of
  readings".
- Trust tests now assert *discrimination*, not just threshold crossing: `HealthConf`
  must rank clean above spiked above frozen with a usable spread, load must not
  scale with window length, and a station losing one parameter must stay more
  trusted than one wholly frozen. These are the properties the existing gates could
  not see.
- Golden recovery asserts R14's injected step *size and instant*, not only that one
  R14 fired. A count-only assertion could not see the localisation bug, and did not.
- ADR 0005: the Enclod canonical mapping - a counter (`uuid`) is a station, a vehicle
  class is a parameter - with the reset discrepancy against the competition brief
  recorded as an open question and a plan rather than a footnote.

### Changed
- `schema_assumptions.yaml` v2: the Enclod block's `counter_column` / `value_column`
  keys described a narrow file shape that does not exist. The real archive is wide
  (one row per counter-tick, ten cumulative measure columns, 42 counters, ~1.53M
  rows); the observed schema is now recorded as such. Per-source `status` gains
  `observed` - columns known, parse not written - and only `confirmed` opens the
  adapter gate, pinned by a test so a config edit alone can never route callers into
  code that does not exist.
- The top-bar lockup renders at 56px (was 28px). `--prov-topbar-height` moves
  56px -> 72px in both `design/tokens/tokens.css` and its `apps/web` mirror so the
  larger mark keeps breathing room against both edges. No artwork, gradient, or
  palette value changed. All sixteen visual baselines regenerated on both
  platforms.
- The primary nav in `TopBar.tsx` gains `ml-6` (`--prov-space-6`, 32px) so the tab
  group reads as its own region rather than sitting against the lockup. No nav
  item, route, or ordering changed. No visual baseline changed - the shift falls
  within the visual gate's pixel-diff tolerance on both platforms.
- **Station detail panel is now resizable, and its default width no longer clips
  the trust-component table.** `--prov-drawer-width` moves 380px -> 520px in both
  `design/tokens/tokens.css` and its `apps/web` mirror - measured, not guessed,
  against the longest realistic content (a full 4-component breakdown, 5 reason
  codes, 7 parameter rows): below ~516px the `<table>` in `TrustBreakdown.tsx`
  (unconstrained auto layout) overflows its container rather than wrapping, which
  is what was cutting off the Value/Weight/Contribution columns. A new drag
  handle (`DrawerResizeHandle.tsx`, `lib/drawerWidth.ts`) sits on the panel's left
  edge from the `lg` breakpoint up: `role="separator"`, keyboard-operable
  (arrow keys, Home/End), double-click resets to the token default, and the
  chosen width persists to `localStorage` (clamped to [360px, 60% of the
  viewport]) and restores on load. The trust-trajectory `Sparkline` now takes a
  `fluid` prop so it scales with the panel instead of staying pinned at a fixed
  320px. Visual baselines regenerated on both platforms: the network map, the
  station detail panel, and the data quality monitor all shift a few px, since
  the resize handle occupies space even in the empty (no station selected)
  state and its neighbouring flex-1 region narrows to match; the event timeline,
  which never renders the drawer, is unchanged.
- **The network map never rendered under `pnpm dev`.** `useMapEngine.ts` carried
  a redundant `useEffect(() => () => engineRef.current?.destroy(), [])` beside
  the callback ref that already owns teardown. React 18 StrictMode
  double-invokes an effect's cleanup once in development, which destroyed the
  engine the ref had just created, with nothing to recreate it - the map was
  stuck on `data-map-state="moving"` forever, bare marker dots over the
  container's own background colour. Removed; the ref callback was always the
  correct sole owner of destroy. A second, independently-found bug: the
  token-ground fallback never re-themed on a dark/light switch, because
  `ThemeProvider` set `data-theme` from a plain `useEffect` and React fires
  passive effects child-before-parent, so the map's style-reapply effect (a
  descendant) always ran before the attribute was written. Fixed by moving that
  one effect to `useLayoutEffect`. Each marker now carries an offset,
  token-styled station-id label beside it, hidden on a genuine screen-space
  collision with a neighbour rather than a guessed zoom cutoff
  (`visibleStationLabels`). The "basemap unavailable" notice now distinguishes
  MapLibre-could-not-start (a browser problem) from tiles-not-fetched (a
  `make basemap` problem) with different wording and a `data-testid` each.
  Visual baselines regenerated on both platforms: only the network map moves:
  the pre-existing `map-*` baselines were themselves showing the fetched
  streets rather than the token ground ADR 0006 says the gate should test,
  because the darwin capture path has no equivalent of the Linux container's
  automatic `public/basemap` removal - recaptured correctly with the archive
  moved aside.

## [1.0.0-demo] - 2026-08-09
Phase 7: the operational layer and the submission build — the freeze tag. Adds the
maintenance queue and Alert Centre, the human sign-off gate on public dispatch, the
completed regulatory export, four-role RBAC, two-plane monitoring, and deterministic
offline demo mode.

### Added
- **PopulationExposure is computed, not stubbed** (`grid/exposure.py`, §7.8). The Risk
  factor is now derived per station from a GTFS static bundle — every stop within a
  ~500 m corridor contributes its distinct-route count, min–max normalised into a bounded
  multiplier — so a broken reading in a busy transit corridor outranks the same fault at a
  rural background site. A station with no coordinate or a drop with no GTFS bundle keeps
  the neutral 1.0 and reports `population_exposure_stubbed=true` (graceful degradation):
  the flag is no longer permanently true. A synthetic GTFS fixture (`fixtures/gtfs.py`)
  gives tests and the offline demo a real bundle to aggregate.
- **Maintenance queue** (`ops/maintenance.py`, `ops/store.py`, §9.5): tickets auto-raised
  from the deterministic fault flags, ranked by **severity × station importance**
  (importance = PopulationExposure), with an `open → acknowledged → dispatched → resolved`
  state machine and a full, append-only transition history. Idempotent rebuild.
- **Alert Centre ranked by RISK, not certainty** (`ops/alerts.py`, §9.5):
  `genuineness × exposure × hazard × confidence`, so a high-exposure **genuine event**
  outranks a confident low-exposure **sensor fault**. Asserted with a constructed pair.
- **Human sign-off gate + idempotent dispatch** (`api/decision/`, §2, standing rule 5):
  every public dispatch passes through one choke point that refuses to send without a
  valid, non-expired operator sign-off (who / when / evidence hash / model version) and
  is idempotent on `(event, channel, sign-off)` — retries and concurrent calls never
  double-send. A **static call-graph test** proves the senders are unreachable except
  through the validated gate.
- **Completed regulatory export** (`report/regulatory.py`, §2): reading accounting, the
  itemised defects and structural exclusions, model versions, sign-off records, and a
  **reproducible verification hash** over the certified content — rendered as CSV, JSON,
  and a dependency-free printable **PDF** summary, all from one bundle. `?format=pdf` and
  an `X-Verification-Hash` header added to `/v1/export/audit-trail`.
- **Four-role RBAC** (`api/auth.py`, §11): adds `admin` above `operator`; a full endpoint
  × role matrix test pins the policy (ADR 0010). An **admin dashboard** surface exposes
  model versions, config hashes, retraining triggers, and export/dispatch history.
- **Two-plane monitoring** (§11): Prometheus service-health metrics at `/metrics` (infra
  plane) and a separate **model-drift monitor** at `/v1/admin/model-drift` (deweathering
  R², conformal coverage, fault confusion, defect-rate drift by station). Grafana
  dashboards and the rationale for the split in `docs/monitoring-v1.0-two-planes.md`.
- **Deterministic offline demo mode** (`cli/demo.py`, `ops/demo.py`, §demo-critical):
  `prov demo run --scenario <name>` replays a fixed window at a controllable speed as an
  ordered sequence of screen states with computed numbers; five scenarios
  (`audit-headline`, `ker11-adjudication`, `contrast-fault`, `deweathering-reveal`,
  `explainability`). Two runs are byte-identical; the suite runs with the network blocked;
  basemap tiles are vendored for the Debrecen bbox. `scripts/record-demo.sh` captures the
  fallback recording.
- **Submission artefacts** (`docs/demo/`): the timed 7-minute `demo-script-v1.0.md`, a
  one-page description, a 3-minute video storyboard, and `judge-questions-v1.0.md`
  (prepared answers to the §16 critiques).

### Tests
- Sign-off architecture (static call-graph), alert risk ordering, dispatch idempotency
  under retry **and** concurrency, the RBAC matrix, audit-export reconciliation + hash
  reproducibility, demo-mode determinism, a full network-blocked offline run, a
  scenario-layer full-script rehearsal, and a 50-client load smoke.

### Fixed
- **A huge integer path parameter no longer 500s.** The maintenance detail/transition
  endpoints are the API's first `int` path params; an id larger than SQLite's 64-bit
  `INTEGER` raised `OverflowError`. A global `OverflowError → 400` handler
  (`api/errors.py`) maps it to a client error, found by the schemathesis fuzz and pinned
  by a regression test.
- **Test databases no longer leak an aiosqlite worker thread.** `io/db/engine.make_engine`
  now backs file-based SQLite (the test path) with a `NullPool`, which closes each
  connection on return, and keeps a `StaticPool` for `:memory:`. This removes at source the
  leftover `_connection_worker_thread` that could race the native OpenMP math pools of a
  later torch-heavy test and segfault the process on macOS (surfaced by the HST-GAT
  "real corpus shape" test once it was included in the full local run; CI-Linux was
  unaffected). Torch is also pinned to a single intra-op thread (`train.py`,
  `tests/conftest.py`) for the CPU determinism the repo already requires (ADR 0009).
- **Phase-6 flag review — the attention export and the calibrated interval are now
  produced in the product flow, not only in tests.** Two capabilities that phase 6 built
  and coverage-tested were reachable only from unit tests:
  - The **attention overlay** (§8) is now written by `prov graph adjudicate --learned`
    (via `models/hstgat/attention.py:write_overlay_for_drop`) as
    `attention_overlay.json` for the top-ranked event — the map-ready "which neighbours
    influenced this call" export. The live MapLibre rendering remains a deliberate
    frontend follow-up (would drift the pinned visual baselines).
  - The **split-conformal calibrator (`q`) is now persisted with the artefact** and
    loaded at inference, so a learned adjudication attaches a **calibrated interval on
    the expected excess of every downwind neighbour** (`NeighbourEvidence.sigma` /
    `expected_interval`) — the "calibrated confidence intervals on every score" the demo
    checkpoint asks for. Previously the model's predictive σ was computed and dropped and
    the `q` was discarded after coverage was recorded. The analytic path is unchanged
    (both fields are `None`; the KER11 characterization still passes byte-for-byte).

## [0.6.0] - 2026-08-09
Phase 6: the research contribution — a heterogeneous spatio-temporal graph-attention
network (HST-GAT), split-conformal intervals, a learned propagation validator behind a
feature flag, and inspectable attention. Sequenced last on purpose: it converged, so it
ships; had it not, Phase 5 would have shipped unchanged.

### Added
- **PyTorch Geometric adaptation** (`graph/pyg.py`) — `GraphSnapshot.to_hetero_data()`
  materialises the same node/edge tables as a PyG `HeteroData` **without any caller
  changing**, with torch imported lazily so the statistics layers still run on a machine
  with no torch. The exact working install (CPU-first, MPS-optional, no compiled
  `torch-scatter`) is recorded in **ADR 0009**.
- **HST-GAT** (`models/hstgat/`, §6.4): `h_i(t) = GRU(h_i(t-1), HetGAT({h_j(t)}, edge_weights(t)))`.
  A hand-rolled heterogeneous graph-attention layer over all five edge types with a
  per-`EnvStation` GRU memory, predicting a **mean and a variance** per station-hour. The
  wind-conditioned weight enters attention as an **additive pre-softmax bias**: zeroing it
  recovers a plain HetGAT (tested), and raising it monotonically shifts attention to the
  wind-connected neighbour (tested). Deliberately small — **3,299 parameters** against 720
  timesteps/station (§5.1) — justified in the model card. A **GCN baseline** is included
  for comparison, as the blueprint specifies.
- **Masked-autoencoder training** (`models/hstgat/train.py`): hide known values,
  reconstruct from wind-weighted neighbours, score with **masked Gaussian NLL**.
  Time-blocked splits (never random K-fold, standing rule 7), full seeding
  (byte-identical reruns on CPU, standing rule 8), and a **run manifest** per training —
  seed, config hash, data checksum, git sha, metrics and parameter count.
- **Split conformal prediction** (`models/conformal/`, §7.7): a small, hand-rolled,
  distribution-free interval with the exact finite-sample quantile and adaptive
  (σ-normalised) width. Every model output gains a calibrated interval; the calibration
  set is always a held-out **time** block. Empirical coverage on held-out data lands
  inside the nominal band (90% nominal → 85–95% empirical, tested).
- **Learned propagation validation, behind a feature flag** (`models/hstgat/forecast.py`).
  The Phase-4 adjudicator's analytic expectation is swapped for the HST-GAT forecast via a
  `graph.ExpectationProvider` Protocol (dependency injection — `graph` never imports
  `models`, so the layering holds). If the artefact is absent or fails to load, the
  adjudicator **falls back to the analytic prior automatically** and the evidence bundle
  records which path produced the verdict (`expectation_provenance`). Both paths stay
  tested and demoable. Flag: `PROVENANCE_LEARNED_PROPAGATION`; CLI: `prov graph adjudicate --learned`.
- **Attention explainability** (`models/hstgat/attention.py`, §8): per-prediction
  attention exported as weighted, highlighted edges — "which neighbours most influenced
  this call" — ready for the network map.
- **Model card** `docs/model-cards/hst-gat-v1.md` (hand-written, committed): parameter
  count, small-data justification, achieved conformal coverage, GCN-baseline comparison,
  honest limitations. Auto-generated per-training cards (checksum-suffixed) are gitignored,
  like the tree models'. New CLI: `prov models train-hstgat`.

### Changed
- The propagation adjudicator (`graph/adjudicate.py`) now takes an optional injected
  expectation provider; the default `AnalyticExpectation` reproduces Phase-4 verdicts
  **byte-for-byte** (the KER11 characterization test is unchanged).

### Explicitly not done (standing rule 4)
- **No headline accuracy or F1 for the propagation validator.** With this few real
  corroborated events such a number would describe the synthetic injection process, not
  the world. The model reports reconstruction NLL/RMSE, per-case evidence, and calibrated
  intervals instead — enforced by a test that scans the metrics for "accuracy"/"f1".

## [0.5.0] - 2026-08-09
Phase 5: meteorological normalization, the supervised fault classifier, and the
explainability layer — completing the B1 → B3 → B2 demo order.

### Added
- **Deweathering (B2)** — one gradient-boosted regressor per pollutant predicts the
  reading from meteorology and time alone; the residual (actual − weather-predicted)
  is what anomaly detection sees downstream. Trained forward-chaining only
  (`models/cv.py`), never random K-fold, and held to a **0.15–0.90 R² sanity band**
  whose two failure modes are named. Residual series are stored in the database
  (`residuals` hypertable) alongside the model version that produced them.
- **Feature layer with honest provenance** (`models/features/`). Wind direction is
  encoded as `(sin, cos)` so 359° and 1° are neighbours, not a cliff at north — a
  property the test gate pins. Temperature/precipitation come from HungaroMet (flagged
  imputed until the feed is confirmed), the boundary-layer height is a documented
  time-of-day/season **proxy** (§5.3), and every feature column carries its provenance.
- **Hybrid fault classifier** (`models/fault/`, §7.3). The deterministic Phase-1
  detectors run **first and short-circuit**; LightGBM only ever chooses among the
  subtle classes (`none`, `calibration_drift`, `meteorological_artefact`). A test
  proves the ML can never override a physical-impossibility flag. Class-weighted
  cross-entropy, a per-class confusion matrix, per-signature recall floors, and a
  watched `meteorological_artefact` precision — **no headline accuracy figure**
  (standing rule 4).
- **Explainability (`explain/`, §8)** — SHAP over the tree models with a stable
  feature-name mapping; the additivity invariant (base + attributions reconstruct the
  prediction) is asserted. A renderer turns attributions into the operator sentence
  ("driven primarily by the shallow overnight mixing layer, then wind speed").
- **`GET /v1/explain/{defect_id}`** serves per-defect SHAP attributions, the fault
  class, the residual and the sentence — degrading to the statistics-layer reason,
  flagged `degraded`, when no model artefact is loaded. **`GET /v1/deweather/{station}`**
  serves the raw-vs-predicted-vs-residual series behind the before/after chart.
- **Model cards, auto-generated at training** (`models/cards.py`, §5): data window,
  feature list with provenance, CV scheme, metrics, class balance, limitations and the
  training-data checksum. A model without a card sidecar (or with a mismatched
  checksum) **refuses to load** (`models/registry.py`).
- **Graceful degradation, end to end** (standing rule 6): with every model artefact
  deleted the API still returns trust scores from the statistics layer, flagged
  `degraded` and complete with their breakdown — pinned by a `demo_critical` test.
- **Dashboard**: the evidence panel's SHAP slot now populates (signed attribution bars
  + the operator sentence), and a toggleable **before/after deweathering chart** (raw
  vs residual) is drawn beside it. Both degrade honestly when no model is loaded.
- **`prov models train` / `prov models residuals`** CLI, and `make demo-models` wires
  training into `make demo` (deliberately not into `make demo-data`, so the pinned
  visual baselines keep their statistics-only state).
- **Real street basemap for the demo map** (ADR 0006, resolving the flag-review
  escalation). `make basemap` extracts the Debrecen region (~6 MB) from a Protomaps
  planet build into a gitignored path; the dashboard renders it under the markers
  when present and falls back to the token ground otherwise. Offline after the first
  fetch, never committed, neutral palette so it never competes with the state colours.

### Fixed
- Second phase-3 flag-review pass:
  - **Defect list truncation is surfaced.** The cursor walk reports when it stops at
    its page cap; the evidence panel shows a banner instead of presenting a prefix as
    the whole set.
  - **The defect table's dense code chip carries its row's evidence**, so its tooltip
    and screen-reader text read the full sentence, not "Value of — — exceeds the
    physical maximum for —".
  - **Trust component evidence keys are pinned pairwise-disjoint** by a test.
  - **The map re-themes on a theme switch** (a latent bug: the token ground never
    repainted), surfaced while wiring the basemap.
- Phase-3 flag-review resolutions:
  - **Trust reason codes carry their figures.** `TrustComponent` gains an `evidence`
    dict keyed by the placeholder names the registry sentences use, and `TrustScore`
    merges them into the substitution map the API now serves as
    `TrustScoreOut.evidence`. No migration: `components` is already a JSON column of
    arbitrary dicts. T03 reads "disagreement with 15 neighbouring station(s)" instead
    of an em dash with a prose fallback beneath it.
  - **The audit report's per-code breakdown is complete.** It read one 500-row page
    and counted it, which on the 18-station demo corpus showed 6 of 13 reason codes
    with R10 at 145 instead of 336. It now reads `summary.defects_by_code`, computed
    by the engine over every row, and `useDefects` follows the cursor so no windowed
    count can silently truncate.
  - **The defect table's code chip carries its row's evidence**, so its tooltip and
    screen-reader text no longer read "Value of — — exceeds the physical maximum
    for —" beside a row holding every one of those numbers.
  - **The contract drift check moved to `ci.yml`**, which has no `paths:` filter and
    therefore cannot be skipped by a change nobody thought to list.
  - **CI starts the API through `make api-bg`**, the same target `make demo` uses, so
    a `make demo` that does not start the API fails a check.
  - Uptime and last-calibration stay derived in the dashboard but are tethered by
    backend tests asserting the two properties their formula assumes.

### Documentation
- `dashboard-v1.1-operator-screens.md` supersedes v1.0.
- `docs/demo/checkpoint-3-capture-checklist-v1.0.md` records the outstanding human
  demo-capture task durably.

## [0.4.0] - 2026-08-09
### Added
- **The heterogeneous graph (`graph/`).** A `GraphSnapshot` value object carries
  node tables (EnvStation, TrafficCounter, BusStop, WeatherNode) and edge tables
  (spatial_proximity, wind_conditioned, road_adjacency, transit_corridor,
  weather_influence) at one timestamp, backed by numpy/pandas today and designed as
  the exact seam phase 6 will back with a PyG `HeteroData` without changing a caller.
  BusStop nodes are **aggregated to a bounded number of corridors** (§16 critique 6),
  enforced by a test. Traffic/bus/weather geometry is honest, clearly-labelled
  `synthetic-provisional` placeholder topology until the Enclod/GTFS feeds are
  confirmed; env-station coordinates and the weather-node centroid are real/computed.
- **Wind-conditioned edge weights** (ADR 0007): `w = exp(-Δθ/sigma_angle) · f(speed)
  · g(distance)`, a lightweight, differentiable **plume approximation, not a
  dispersion model**. Geodesic bearings and haversine distance on a sphere; correct
  angular wraparound at the 0/360 seam; a saturating speed response and a distance
  decay. Zero wind produces a degenerate but finite graph (no NaN, no division by
  zero). Station-local wind with a **city-level HungaroMet fallback** (KER15 carries
  no wind sensor), provenance tracked per edge.
- **Analytic propagation expectation**: expected arrival delay, attenuated
  magnitude, and an expected series over a 15–60 min horizon, bucketed to the hourly
  cadence (documented, not interpolated).
- **The propagation adjudicator (`graph/adjudicate.py`)**: `validate_event()` returns
  `GENUINE_EVENT` / `LIKELY_FAULT` / `AMBIGUOUS` with a confidence and a full
  `EvidenceBundle` (wind, downwind neighbours + weights, expected vs actual, match
  score, covariate state, reason codes). **AMBIGUOUS is first-class** — it routes to
  human review and can never render as high confidence, enforced in the value object.
  Reason codes R22 (PLUME_CORROBORATED) and R23 (ADJUDICATION_AMBIGUOUS) join the
  registry under a new `adjudication` category; the fault case surfaces R17. **No
  headline accuracy figure is reported** (standing rule 4) — see the model card.
- **Replay harness (`graph/replay.py`)** and `prov graph adjudicate` / `snapshot` /
  `adjudicate-db`: rank the corpus's candidate events by magnitude and anomaly,
  adjudicate each, and write evidence bundles to `reports/adjudications/`. Pointed at
  the real drop the top event is the ~4,100 µg/m³ KER11 spike, surfaced by ranking —
  no station or verdict is hardcoded, hinted at, or assumed anywhere.
- **Dashboard**: the wind-conditioned edge layer is enabled on the map (opacity/width
  by weight, direction shown); the event timeline colours each verdict and opens a
  full **event detail** — expected vs actual downwind series, verdict + confidence,
  downwind neighbours, and the covariate stubs; verdict labels populate for
  adjudicated events. Stored events are adjudicated back into `Event.verdict` and
  `Event.evidence.adjudication` by a graph-layer persister (io/db stays upstream of
  graph), so the API serves them with no contract change.

### Documentation
- ADR 0007 (wind edges), `docs/model-cards/propagation-adjudicator-v1.md`.

## [0.3.0] - 2026-08-08
### Added
- **Dashboard v1** (`apps/web`) — the operator-facing second screen, and the first
  complete demoable product. Vite + React 18 + TS strict, TanStack Query, React
  Router, MapLibre GL, Recharts, Tailwind reading the design tokens.
  - **Network map**: 18 station markers coloured by trust (green > 0.85, amber
    0.5–0.85, red < 0.5) and *shaped* by trust as well, so colour is never the only
    channel. Wind vector overlay (circular mean, so the 360/0 wrap does not point
    the arrow backwards), event glyphs on actively-flagged stations, layer toggles
    with the wind-conditioned-edge layer built disabled and explained.
  - **Station detail**: trust score with its component breakdown and its reason
    codes as plain-language sentences, per-parameter sparklines that break at gaps
    rather than interpolating, structural-absence coverage notes, and
    [View evidence] / [Acknowledge] / [Dispatch] — the last two writing to a local
    queue that has no transport out of the browser (standing rule 5).
  - **Data quality monitor**: dense, sortable, filterable, virtualised table.
    Uptime is derived as 1 − (R01 absent cells ÷ expected cells) and the last
    calibration epoch from the newest R15 discontinuity; both derivations are
    stated on screen next to the number.
  - **Event timeline**: events on a time axis, coloured *and* shaped by
    classification. Every verdict reads "pending adjudication" until phase 4.
  - **Evidence panel**: reason-code sentence, the detector's own evidence numbers,
    the raw series ±24h with the flagged point marked, and the neighbouring
    stations measuring the same parameter. SHAP and attention render as explicit
    "not yet computed" slots.
  - **Audit report**: the phase-1 report rendered natively, with the defect-rate
    definition displayed beside the number and drill-down by reason code.
- Generated frontend contract (`scripts/gen_frontend_contract.py`): OpenAPI schema,
  the reason-code registry including every operator sentence, and the numeric design
  tokens the UI branches on. `--check` is the CI drift gate — nothing about the API,
  the registry, or the palette is restated by hand in TypeScript.
- 18-station demo corpus: `prov fixtures make --stations N` appends clean stations
  beyond the four the injection layout targets, and writes a `stations.json` sidecar
  carrying synthetic coordinates. `make demo` loads it, audits it, and opens the
  dashboard; the four-station test corpus and its golden ledger are unchanged.
- Reversed horizontal lockup (`design/logo/provenance-lockup-horizontal-reversed.svg`),
  generated from the approved lockup by substituting only the wordmark's ink for
  `--prov-white`. The approved lockup's near-black wordmark is invisible on the dark
  theme, which is the default. Geometry equality is asserted by a brand test.
- CORS on the API (`PROVENANCE_CORS_ORIGINS`, an allow-list, never `*`). The
  dashboard is a browser client on another origin; without this every request fails
  preflight and every screen renders empty against a perfectly healthy API.
- Test gate: 152 Vitest component tests (94.7% line coverage on `apps/web/src`,
  gate 80%), and 51 Playwright end-to-end tests covering the demo path, axe-core
  scans of every route in both themes with zero critical violations, keyboard-only
  traversal, visual regression baselines for four screens in both themes, and the
  390px responsive floor.

### Changed
- Phase-2 flag-review escalation decisions (both Option A):
  - **Trust weights endorsed.** `trust_weights.yaml → status: endorsed` (project lead,
    2026-08-08), backed by real-event evidence: on the real export the weights drop
    DEB-KER11's trust 0.577 → 0.275 at the 4100.7 µg/m³ PM10 event (T04), recovering
    once it leaves the window. Endorsement ≠ logistic refit; the compressed real-data
    distribution and "discrimination lives in the series" caveat are recorded in the
    config and in methodology **v1.2** (supersedes v1.1).
  - **zone_type populated** from a curated, provisional `config/station_zones.yaml`
    (16 stations classified urban/suburban/industrial/background from site names, each
    with a rationale + confidence, `status: provisional`). Never inferred from
    readings; fixtures stay null.
- Phase-2 flag-review resolutions:
  - Trust scores are persisted as a **daily series** across the ingest window, not a
    single instant, so `/v1/trust/{id}?series=true` returns a real trajectory
    (`trust_weights.yaml → scoring`). Superseding methodology doc
    `trust-score-methodology-v1.1-invariants-and-series.md`.
  - Station **name and coordinates** now populate from the Green Sentinel `Location`
    column (verified real format `"<name> (lat, lon)"`, parsed by
    `io/loaders.parse_location`, failing loudly otherwise); the PostGIS `geom` point
    is now a STORED generated column derived from lat/lon. `zone_type` stays null —
    it has no source in the export (recorded in `schema_assumptions.yaml`).
  - `quality/summary.last_reading_at` now reports the real per-station max reading
    time instead of null.
  - The engineering-judgement trust formulas are pinned by invariant tests
    (`tests/unit/test_trust_invariants.py`): HealthConf monotonicity, plausibility
    ceiling-softening, Trust = weighted sum, scoring-instant cadence/cap/anchor.

## [0.2.0] - 2026-08-08
### Added
- Persistence layer (`io/db/`): SQLAlchemy 2.0 async ORM for stations, parameters,
  readings, defects, audit_runs, coverage_facts, trust_scores, events, and
  ingest_batches. Every persisted row carries the `ingest_batch_id` / `audit_run_id`
  that produced it — provenance of the data is the schema.
- Alembic migrations against TimescaleDB + PostGIS: `readings` and `trust_scores`
  are hypertables chunked by day; `stations` carries a `geometry(Point,4326)`
  column. The ORM stays portable (SQLite for the fast test path); the
  Postgres-specific DDL lives in the migration and is proven by a Dockerised
  up/down/up round-trip test.
- Idempotent loader keyed on the data checksum: re-loading the same file changes
  nothing (asserted by test). `prov db upgrade`, `prov db load`, `prov db reset`.
- Trust Score v1 (`trust/`), statistics-only, implementing §7.8:
  `Trust = w1·HealthConf + w2·(1−ImputationUncertainty) + w3·CrossSensorConsistency
  + w4·PhysicalPlausibility`. Weights in `config/trust_weights.yaml`, elicited and
  documented as pending a logistic refit. ImputationUncertainty is an explicit,
  flagged placeholder. `Risk = Trust × SeverityVsThreshold × PopulationExposure`
  with PopulationExposure stubbed at 1.0 and flagged, not silently defaulted.
- A `TrustScore` cannot be constructed without its component breakdown and a reason
  code; `TrustScoreOut` requires both non-empty; an architecture test proves no
  response model exposes a station trust value without them (standing rule 9).
- Trust reason codes T00–T05 in the registry (category `trust`, non-counting).
- FastAPI application (`api/`), async, auto OpenAPI: stations, readings (raw and
  quality-flagged), defects, trust (point-in-time and series), quality summary,
  events (verdict null until Phase 4), audit runs, the regulator-facing
  audit-trail export (CSV + JSON, reproducible and reconciled), and healthz/readyz/
  version. Cursor pagination, RFC 7807 problem responses, structured request
  logging with a request id, and API-key auth with three roles
  (operator/researcher/public_read).
- Ingestion abstraction (`io/ingest/`): an `IngestAdapter` Protocol with the
  Green Sentinel adapter fully wired and Enclod/HungaroMet/GTFS as discover-only
  adapters that fail loudly while their schemas are unconfirmed. A streaming adapter
  can be added with zero changes downstream (ADR 0003).
- Tests: trust component units, the perfect-station >0.95 / frozen-station <0.5
  gate, an endpoint × role auth matrix, pagination traversal invariants, byte-for-
  byte audit-trail reproducibility with defect-count reconciliation, a schemathesis
  fuzz asserting no endpoint 5xxs, idempotent-load, and Dockerised migration and
  full-stack integration tests. Coverage gate raised to 88%.
- ADR 0003 (ingestion abstraction), ADR 0004 (API-key auth now, OIDC deferred to
  phase 7), `docs/api/README.md` with worked curl examples, and
  `docs/trust-score-methodology-v1.0.md`.

## [0.1.0] - 2026-08-08
### Added
- The statistics-only audit engine (B1) — the demo's opening block and the
  no-ML fallback the whole project rests on. No machine learning.
- Canonical long frame (`schema/`): pandera-validated, deterministic `row_hash`,
  observed-schema discovery writing a manifest per data drop.
- Green Sentinel loader (`io/`): reads the real Hungarian-schema Excel export,
  fails loudly on schema drift, never invents a field name or unit.
- Cumulative traffic-counter repair (`io/counter_repair.py`): reset-aware
  differencing with an exact difference/cumulate round-trip; detects resets
  (R05), non-monotonic runs (R06), duplicate timestamps (R03), out-of-order
  rows (R04), and dead sensors (R21).
- Coverage model (`grid/`): per-series cadence inference and four separately
  reported quantities — observed, absent, structurally-excluded, expected — with
  `expected == observed + absent + structurally_excluded` enforced by property
  tests. Structural absence is inferred from the data, not hardcoded.
- `DefectRate` — the single defect-rate definition in the codebase, rendered
  next to every number it produces.
- Detectors R01–R14, R18, R19, R21, each a pure function over the canonical
  frame with a JSON-serialisable evidence dict; all thresholds live in
  `config/thresholds.yaml` with a cited physical or statistical basis.
- Audit orchestrator (`audit/`) producing an `AuditResult` with run metadata,
  coverage summary, by-code/station/parameter/day breakdowns, structural
  section, and a ranked `notable_events` list.
- Reporting (`report/`): deterministic `audit.json`, `audit.md`, and a
  self-contained printable `audit.html` that inlines the design tokens.
- Seeded synthetic corpus generator (`fixtures/`) with a ground-truth ledger;
  the golden recovery test asserts the audit reproduces every injected count
  exactly, and the clean corpus trips no detector.
- CLI: `prov data profile`, `prov schema observe`, `prov audit run`,
  `prov audit report`, `prov fixtures make`.
- `docs/audit-methodology-v1.0.md`: every detector, its threshold, its
  justification, and the defect-rate definition.

### Changed
- Config confirmed against the real export: `schema_assumptions.yaml` status is
  now `confirmed`; `thresholds.yaml` status is now `calibrated`.

## [0.0.2] - 2026-08-08
### Added
- CI: dedicated `architecture` job running the structural-invariant tests on
  their own, so a layering violation surfaces as its own PR check.
- Brand guardrail: `tests/architecture/test_brand.py` fails if the app's token
  file drifts from the authoritative `design/tokens/tokens.css` (byte-identical).
- Brand guardrail: frontend `no-inline-hex` test fails if any hex colour literal
  appears in `apps/web/src` outside `styles/tokens.css`.
- ADR 0002: licensing recorded as provisional (MIT), with the triggers that would
  force a change and who decides.

### Changed
- `test_no_data_files_are_tracked` now checks git's index rather than the
  filesystem, so it passes with untracked real data present locally (required
  from phase 1) while still failing if data is ever committed.

## [0.0.1] - 2026-08-07
### Added
- Repository scaffold: src-layout Python package, monorepo directory structure.
- Tooling: uv, ruff, mypy (strict), pytest with coverage gate, pre-commit.
- CI: GitHub Actions for backend, frontend, and CodeQL.
- Docker Compose stack: TimescaleDB (Postgres 16 + PostGIS), Redis, api, web.
- Reason-code registry (R01-R21) seeded from the dataset profiling findings.
- Brand assets: the approved logo rebuilt as vectors (mark, small-size
  reduction, one-ink, horizontal and stacked lockups, app icon).
- Design tokens carrying the agreed Trust Blue / Sentinel Green / Alert Amber
  palette, unchanged by the logo. The mark's own artwork values are scoped
  separately as `--prov-brand-*` and are not usable in the interface.
- ADR 0001: monorepo and stack.
