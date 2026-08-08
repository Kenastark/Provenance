# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]

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
