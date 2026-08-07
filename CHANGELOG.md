# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]

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
