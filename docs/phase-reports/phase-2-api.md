## Phase 2 - Storage, Trust Score, and the API

Date: 2026-08-08. Branch: `phase-2-api`. Tag: `v0.2.0`.

### What was built

Persistence, the first Trust Score, and the public API surface — still no machine
learning. A SQLAlchemy 2.0 async ORM and Alembic migrations put the audit's output
into TimescaleDB (readings and trust_scores as day-chunked hypertables, stations
carrying a PostGIS point), with every row tagged by the ingest batch or audit run
that produced it, and an idempotent loader keyed on the data checksum. The
statistics-only Trust Score v1 (§7.8) computes four explained components plus a
Risk figure, and cannot exist as a bare number. A FastAPI application exposes
stations, readings (raw and quality-flagged), defects, trust, quality summary,
events, audit runs, and a reproducible regulator-facing audit-trail export, behind
API-key auth with three roles, cursor pagination, RFC 7807 problems, and structured
request logging. An `IngestAdapter` abstraction makes Green Sentinel one wired
source among four, with a streaming adapter addable downstream-free.

### Test gate

`make check` (ruff + ruff format + mypy --strict + pytest) is green.

- **239 passed**, 2 deselected (the Docker-gated tests), on the default suite.
- **Coverage 93.09%**, over the raised 88% gate.
- Trust: per-component unit tests; the perfect-station **>0.95** (scores 1.0) and
  frozen-station **<0.5** (scores 0.45) gate; every response carries components and
  a reason code.
- Architecture: no response model exposes a station trust value without its
  components and reason codes; the `TrustScore` value object enforces the same.
- API contract: schemathesis fuzz over every operation asserts no endpoint 5xxs;
  an endpoint × role auth matrix; pagination traversal visits every row once; the
  audit-trail CSV is byte-for-byte reproducible and its row count reconciles with
  the defects table.
- Idempotent load: loading the same fixture twice leaves row counts unchanged.
- **Docker-gated (`needs_docker`), run against the live TimescaleDB container and
  both passing:** the Alembic up/down/up round trip (verifying the two hypertables
  and the PostGIS geom column), and the full-stack migrate → load → serve → hit
  every endpoint integration test.

### Deviations from the prompt

- **`RiskOut.trust` and the quality tile.** The architecture rule "no serialiser
  emits a trust score without components" is enforced against *station-scoped*
  score payloads (a model with both `station_id` and `trust`). `RiskOut` carries a
  `trust` scalar that is a formula input, only ever nested inside a fully-explained
  `TrustScoreOut`, so it is correctly excluded. The quality-summary tile *does*
  carry a station trust value, so it was given the full components + reason_codes
  rather than being allowed to render a bare number — a stricter reading of the
  rule than the prompt spelled out.
- **API-key auth deferral recorded as ADR 0004** (the prompt asked for an ADR on
  the OIDC deferral); the ingestion ADR is 0003 as instructed.
- **schemathesis** advertises OpenAPI 3.0.2 for the fuzz only (FastAPI emits 3.1,
  which schemathesis 3.x cannot parse); production still serves 3.1. The fuzz
  asserts the high-value property (no 5xx) rather than full schema conformance,
  because the RFC 7807 problem responses are intentionally not enumerated per
  operation.
- **Enclod/HungaroMet/GTFS adapters are discover-only**, failing loudly
  (`SchemaDriftError`/`SourceNotReady`) because their schemas are still
  `unconfirmed` in `schema_assumptions.yaml`. This honours standing rule 2 rather
  than inventing column names; only Green Sentinel is fully wired, as in phase 1.

### Flag for review

- **Trust weights are elicited, not fitted, and the numbers are load-bearing.** The
  perfect/frozen thresholds pass comfortably, but the exact component formulas
  (HealthConf's `exp(-load/3)`, the plausibility upper-margin softening, the
  cross-sensor [-1,1]→[0,1] mapping) are engineering judgement, not calibration.
  They should be revisited when labelled events exist — recorded in
  `docs/trust-score-methodology-v1.0.md`.
- **Trust scores are persisted at one instant per load** (the window end). The
  `/v1/trust/{id}?series=true` endpoint is real but returns a single point until a
  future phase scores a rolling series. The contract is right; the data is thin.
- **Station geometry/zone_type/name are null in v1.** The Green Sentinel `Location`
  column (site name + lat/lon) is not yet parsed into the stations table, so the
  PostGIS `geom` column exists but is unpopulated. Worth wiring before the map-heavy
  dashboard work in phase 3.
- **`quality_summary` last_reading_at is always null** — the coverage matrix carries
  counts, not timestamps. Reported as unknown rather than invented; a cheap follow-up
  if the DQM tile wants it.
