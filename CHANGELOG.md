# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]
### Added
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
