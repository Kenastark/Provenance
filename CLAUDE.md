# CLAUDE.md

Read this before doing anything in this repository.

## What this is

**Provenance** — an AI trust and quality-assurance layer for Debrecen's Green
Sentinel environmental sensor network (16 land monitoring stations + 2
surface-water points), built for the DEIK.AI Challenge 2026, entry track 2B.

Product descriptor: *AI Trust Layer for Environmental Data.*
Spoken demo hook, used on stage and on the title card only: *"Is This Real?"*

The thesis in one sentence: **a number on a screen looks exactly the same whether
it is true or broken.** 149,683 readings over 30 days at roughly 99.95%
completeness — by every conventional measure this network is perfectly healthy,
and it isn't. Provenance finds the readings that are present, well-formed,
plausible, and wrong, and explains why.

This is not a replacement for Green Sentinel's public dashboard. It is the
operator-facing second screen that scores every reading for genuineness.

## Standing rules

These matter more than any individual feature. Several are enforced by tests in
`tests/architecture/`.

1. **Never hardcode a number that should come from the data.** The defect rate,
   the completeness percentage, station counts, the verdict on the ~4,100 µg/m³
   event — all are computed outputs. If a number appears in a report, a test, or
   the UI, there must be a code path that derives it from a dataset.
2. **Never invent field names or units.** If the real schema is unknown, read it
   from the file at runtime and fail loudly on mismatch. Assumptions live only in
   `src/provenance/config/schema_assumptions.yaml`, marked with their status.
3. **Structural absence is not a defect.** A station that never carried a wind
   sensor is a coverage fact. These are excluded from both the numerator and the
   denominator of the defect rate and reported separately. Getting this wrong
   inflates the most scrutinised number in the pitch.
4. **Never report a headline accuracy figure for the propagation validator.**
   With this few real positives, such a number describes the synthetic injection
   process, not the world. Report per-case evidence and calibrated intervals.
5. **No code path may publish a public-facing alert without a human sign-off
   record.** Enforced by an architecture test from phase 7. This is an ethical
   commitment, not a preference.
6. **Graceful degradation is a requirement.** If a model artefact is missing, the
   system still produces a trust score from the statistics layer and says so in
   the response.
7. **Tests never require the real dataset.** Everything runs against the seeded
   synthetic corpus in `tests/fixtures`. CI is green on a fresh clone with an
   empty `data/`.
8. **Determinism.** Seed everything. Two runs over the same input produce
   byte-identical reports.
9. **A trust score never renders without its component breakdown and at least one
   reason code.** Not a UI preference — it is what separates a trust layer from a
   black box that says trust me.
10. **Documents are versioned, never edited in place.** `docs/` files follow
    `name-vX.Y-descriptor.md`. A revision is a new file that says what it
    supersedes.

## Build order — do not reorder

Each phase leaves a demoable system. The statistics-only audit ships **before**
the graph work so that a slip in the hard weeks costs ambition, not viability.
Building the impressive part first is the tempting mistake and the wrong one.

| Phase | Adds | Tag |
|---|---|---|
| 0 | Repo, CI, Docker, test harness | `v0.0.1` |
| 1 | The audit engine (B1), CLI, HTML report | `v0.1.0` |
| 2 | TimescaleDB, Trust Score v1, FastAPI | `v0.2.0` |
| 3 | Dashboard v1 — first complete demo | `v0.3.0` |
| 4 | Wind-conditioned graph + analytic adjudicator (B3) | `v0.4.0` |
| 5 | Deweathering (B2), LightGBM fault classifier, SHAP | `v0.5.0` |
| 6 | HST-GAT, conformal prediction, attention overlay | `v0.6.0` |
| 7 | Alerts, sign-off, RBAC, monitoring, demo hardening | `v1.0.0-demo` |

Demo block order on stage: **B1 (audit) → B3 (graph adjudication) → B2
(deweathering)**, with the industrial-attribution angle as a 20-second closing
slide and no live query.

## Stack

Python 3.12 · uv · pandas · pandera · Typer · FastAPI · TimescaleDB (Postgres 16
+ PostGIS) · Redis · LightGBM · PyTorch + PyTorch Geometric · React 18 +
TypeScript + MapLibre GL · Docker Compose · GitHub Actions.

MapLibre rather than Mapbox, deliberately: a municipal buyer story is stronger on
an open stack.

## Brand

The palette is fixed: Trust Blue (chrome and interaction), Sentinel Green
(verified), Alert Amber (anomaly and ambiguity), Signal Red (fault), cool
neutrals. It lives in `design/tokens/tokens.css` and is mirrored into
`apps/web/src/styles/tokens.css`. **No colour or type value belongs anywhere in
the application except as a token reference.** Blue is the only interactive
colour; green, amber and red mean state.

Logo assets are in `design/logo/`. The mark's three artwork values
(`--prov-brand-*`) are for the mark only and never for the interface.

## Commands

    make install      # create .venv and install with dev extras (uv)
    make check        # lint + mypy strict + pytest with the coverage gate
    make test         # tests only
    make up / down    # local stack
    make demo         # stack + fixtures + audit + dashboard
    prov codes list   # the reason-code registry

## Layering

    io -> schema -> grid -> detectors -> audit -> trust -> graph -> models -> explain

`api` and `report` are presentation layers and are never imported by anything
upstream. `tests/architecture/test_layering.py` enforces this with an import-graph
check, because conventions decay under deadline pressure and tests do not.

## Working agreements

- Branch `phase-N-<slug>` off main, PR into main, squash merge, tag on main.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`).
- Every PR: tests for new behaviour, coverage held, `CHANGELOG.md` entry, docs
  updated as a new version file, no data-derived constants.
- Any decision expensive to reverse gets an ADR in `docs/decisions/` before the
  code lands.
- Do not skip a phase's test gate to reach the next phase faster.

## Never do this

1. Hardcode the defect rate, the completeness figure, or the event verdict.
2. Invent field names, units, or station identifiers not observed in the data.
3. Count structural absences toward the defect rate.
4. Emit a trust score without components and a reason code.
5. Report a headline accuracy figure for the propagation validator.
6. Let the ML fault classifier override a deterministic physical-impossibility flag.
7. Use random K-fold cross-validation on any time series.
8. Reach a public-alert dispatch without a recorded human sign-off.
9. Edit a versioned document in place instead of writing the next version.
10. Commit anything under `data/raw`, `data/interim`, or `data/processed`.
