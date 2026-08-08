# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]
### Changed
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
