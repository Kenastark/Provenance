# Update 13 — four small items from the phase reports

Branch: `update-12-polish`. Tag: `v1.0.14-update`.

**Naming deviation, flagged up front:** the prompt asked for doc `u12-polish.md`
and tag `v1.0.13-update`. Both are already taken — `docs/updates/u12-enclod.md`
(branch `update-11-enclod`) shipped as `v1.0.13-update` immediately before this
work started. This report and its tag take the next free slot (`u13`,
`v1.0.14-update`); the branch name is kept exactly as given, since it was free.
Per the working agreement for these reports, numbers below are copy-pasted from
real command output, not retyped or rounded by hand.

## 1. R14 step-change direction label — already fixed, no code change

The prompt describes a bug where `detectors/step_change.py` could label a clearly
upward step "downward" because the CUSUM crosses the low side first when the
whole-series mean sits above the pre-step level. That bug existed, but it was
already fixed — in PR #3 (`7f41535`, "fix: unsaturate HealthConf and localise step
changes correctly"), well before this branch. The current detector has no
`direction` field at all: it reports `signed_magnitude`/`level_before`/
`level_after` from a changepoint located by the split maximising the difference of
means, independent of which CUSUM arm crossed first. The exact regression test the
prompt asks for already exists —
`test_r14_signed_magnitude_agrees_with_the_direction_of_the_step` in
`tests/unit/test_detector_step_change.py` — built from a series that reproduces the
old behaviour (an upward and a downward step, asserting the sign of
`signed_magnitude` and that `"direction" not in evidence`). The fix is also
recorded as a versioned methodology revision,
`docs/audit-methodology-v1.1-step-change-localisation.md`, with the exact
before/after numbers on the fixture's injected +15.0 µg/m³ step. I checked the full
diff history of `step_change.py` for any later reintroduction of a `direction`
field — none. No code changed for this item; verified only.

## 2. Contract-check path filter — already fixed, no code change

The prompt describes the reason-code contract drift check living behind
`frontend.yml`'s `paths:` filter, so it wouldn't run on a branch that edits the
registry without touching a frontend file. This was also already fixed — in the
phase-3 flag review (`6f9360f`, PR #5, "Flag 2. The contract drift check moves to
ci.yml, which has no `paths:` filter"). The `contract` job lives in `ci.yml` today,
which has no `paths:` block on either its `push` or `pull_request` trigger, and is
pinned by an architecture test,
`test_contract_drift_check_runs_in_an_unfiltered_workflow` in
`tests/architecture/test_brand.py`, which parses every workflow file and fails if
any workflow defining a `contract` job filters its `pull_request` trigger by path.
No code changed for this item; verified only (`tests/architecture -q`: 50 passed).

## 3. Uptime and calibration epoch move into the audit engine

`QualityMonitor.tsx`'s `buildRows` computed `1 - (R01 absent cells / expected
cells)` and took the newest `R15` discontinuity as the calibration epoch,
client-side, off the `/v1/defects` list — flagged in the phase-3 report's flag
review as business logic sitting in a presentation layer, tethered only by two
backend pinning tests (`tests/unit/test_uptime_assumptions.py`) asserting the
formula's silent assumptions (every series is hourly; R01 is one flag per absent
cell).

**What moved.** `io/db/repository.py::quality_summary` now computes both figures
server-side, windowed by the same `start`/`end` `/v1/quality/summary` accepts as
query params — mirroring how `/v1/defects` is already windowed. `QualityStationOut`
gains `uptime_pct`, `absent_cells`, `expected_cells`, `last_calibration_at`.
`QualityMonitor.tsx`'s `buildRows` is now just the station/meta join; the frontend
displays what it is given rather than re-deriving it. `test_uptime_assumptions.py`
keeps its two invariant tests (still exactly what the backend formula depends on)
but now names `repository.py::quality_summary` as the fix location instead of the
frontend file.

**A finding surfaced along the way, not part of this item's scope:** R15
`CALIBRATION_EPOCH_DISCONTINUITY` has no detector implementation anywhere — it's
registered in `reason_codes.py` but never in `default_detectors()`. This was already
true before this change (the old frontend derivation queried an endpoint that always
returned zero R15 defects); moving the computation server-side does not fix or mask
that — `last_calibration_at` reads honestly as `None` until an R15 detector exists.
Recorded here as a flag for review, not silently worked around.

**Tests.** Three new integration tests in `tests/integration/test_api_endpoints.py`
pin the windowed behaviour against the real fixture corpus: uptime is `None` with no
bounded window; a 168-hour window over `STA-01` recovers exactly 5 absent cells
(the fixture's known scattered CO2 absences at hours 30/60/90/120/150) with
`expected_cells`/`uptime_pct` matching the formula; `last_calibration_at` reads
`None` everywhere (consistent with the R15 finding above). On the frontend,
`QualityMonitor.test.tsx`'s derivation-arithmetic tests are replaced with tests for
the (now trivial) station/meta join, plus two render-path tests proving the served
figures pass through unchanged and the null/no-window state still reads as an em
dash and "none detected". Frontend contract regenerated
(`openapi.json`, `schema.d.ts`).

## 4. PopulationExposure — provisional marker wherever displayed

The normalisation method is unchanged, as instructed — still min-max across the
stations in the current drop, still `status: provisional` in `config/graph.yaml`.
What changed is visibility: every screen that displays the figure now says so.

- **Alert Centre** — the risk-factor table's Exposure column header reads
  "Exposure (rel.)", with a tooltip (`DataTable`'s new optional `headerHint`)
  explaining the relative, drop-dependent normalisation.
- **Alert detail** — the risk-factor breakdown's Exposure row carries the same
  label and hint (`FactorBreakdown`'s new optional `Factor.hint`, rendered as a
  native tooltip on the row label).
- **Maintenance queue** — the ticket detail's "Station importance" factor is the
  same PopulationExposure figure under a different name
  (`ops/maintenance.py`: `importance` "maps station id → PopulationExposure
  factor"); relabelled "Station importance (rel.)" with the same hint.
- **Model card** — `docs/model-cards/propagation-adjudicator-v1.md` (the card
  whose `Config:` field is `config/graph.yaml`, the same file exposure's
  parameters live in) gains a "Known failure modes" bullet stating the
  cross-network non-comparability explicitly, alongside the existing
  provisional-parameters bullet.

No detector, no formula, no config value changed.

## Test gate

- Backend: `.venv/bin/ruff check`, `ruff format --check`, `mypy` — clean.
  `pytest` (full suite, no marker filter): **683 passed**, coverage **90.58%**
  (gate 88%). `pytest tests/architecture -q`: **50 passed**.
- Frontend: `pnpm lint`, `pnpm typecheck` — clean. `pnpm test:coverage`: **276
  passed**, coverage gate held.
- Frontend contract: `gen_frontend_contract.py --check` current; `schema.d.ts`
  self-consistent with a fresh `pnpm gen:types` (verified by diffing two
  consecutive regenerations — no drift).
- E2E, both platforms (darwin native + the pinned `mcr.microsoft.com/playwright`
  Linux image, against a `docker compose down -v`-fresh database, local trained
  model artefacts moved aside for the capture and restored after): visual
  regression **12/12** on each platform, `demo-path` + `accessibility` **35/35**,
  `signoff-flow` + `drawer-resize` **6/6**, mobile `responsive` **9/9**.

**On baselines:** items 3 and 4 both touch screens under visual regression
(`quality-monitor-*.png`, `alert-centre-*.png`). Neither actually moved the
baselines. Item 3's served uptime/calibration figures are the *same* formula over
the *same* data as before — only where it's computed changed, so the rendered
numbers are pixel-identical. Item 4's label-suffix-and-tooltip additions fall under
the visual gate's own tolerance (`maxDiffPixelRatio: 0.002`) — confirmed by running
the *non-update* check (`pnpm e2e`, `make web-visual-check`) clean against the
pre-existing baselines, not just skipping regeneration.

**One baseline pair did change, unrelated to items 1–4:** the committed
`station-detail-{dark,light}-chromium-darwin.png` had been captured with locally
trained model artefacts present (masking the "Degraded mode — statistics layer
only" banner that a fresh clone or CI always shows against the demo corpus, which
`make demo-data` deliberately never trains models for — the same class of staleness
[[e2e-visual-baselines-gotcha]] describes). Following the documented capture
procedure for this session (artefacts moved aside, restored after) corrected them
to the true degraded state. Linux's equivalent baselines were already correct;
only darwin's needed it.

## Deviations from the prompt

- Doc/tag numbering (see above).
- Item 3 required deciding how to keep the uptime figure's time-window semantics
  when moving it server-side: `/v1/quality/summary` gained optional `start`/`end`
  query params (mirroring `/v1/defects`) rather than becoming unwindowed. This
  preserves the existing 24h/7d/corpus window behaviour exactly.
- The R15-detector-does-not-exist finding (item 3) is out of scope for this
  update and is flagged above rather than fixed.

## Flag for review

- **R15 `CALIBRATION_EPOCH_DISCONTINUITY` has no detector.** It's a registered
  reason code with a message template and a severity, never wired into
  `default_detectors()`. `last_calibration_at` is honestly `None` everywhere until
  one exists. Worth deciding whether phase 8+ needs this detector, or whether the
  reason code and the now-served field should be documented as aspirational until
  it does.
- Items 1 and 2 being already-fixed suggests the source "phase reports" this
  prompt drew from were the *original* phase reports, not their later flag-review
  passes. Worth checking whether any other outstanding "flag for review" items
  circulating are similarly already closed before another polish pass is queued
  from the same source.
