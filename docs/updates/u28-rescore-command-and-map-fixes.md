# Update 28 — rescore stale trust scores, fix the DEB-KER12 map race

Date: 2026-09-01 · Branch: `update-28-rescore-command-and-map-fixes` ·
Tag: `v1.0.29-update`

Three problems, found while chasing one user report ("DEB-KER01/04/06/08 show
fault locally but only 06/08 show fault live, and DEB-KER12 still doesn't render
correctly on load"). All three are described in full investigative detail
earlier in this session; this doc records the fixes actually shipped.

## 1 — production's trust scores were frozen from before its models existed

**Diagnosis.** Verified live, not assumed: production's `provenance-api` and
`provenance-tasks` (Cloud Run Job) already share a GCS-FUSE-mounted artefact
bucket (`provenance-506423-provenance-artefacts`), and the bucket genuinely
holds real, checksum-matching imputation models (`.pt` artefacts, confirmed via
direct file listing and content). Despite that,
`/v1/quality/summary` kept reporting `ImputationCertainty` as a statistics-only
placeholder for every station. Root cause: that endpoint reads a `TrustScore` row
computed **once**, synchronously, inside `prov db load` - and the specific run
being served was loaded at `2026-08-31T11:59:01Z`, while the matching model
artefacts were not written to the bucket until `13:54Z`/`17:02Z` that same day.
The load correctly degraded to the placeholder at the time (standing rule 6
working as designed); nothing ever recomputed it once training finished. `db
load`'s idempotency check has no path for "the data's unchanged but I'd like
this rescored" - it only ever short-circuits with `already_loaded=True`.

**Fix.** New command, `prov db rescore --source <path>`
(`io/db/loader.py::rescore_frame`, `migrate.rescore`, wired into the CLI).
Requires the drop to already be loaded (raises `BatchNotLoadedError`
otherwise), deletes and reinserts only the `TrustScore` rows for that run against
whatever's on disk right now - readings, defects, coverage facts and events are
never touched, and nothing is retrained. Full reasoning and the three-operation
model (train / load / rescore) this keeps distinct: `docs/decisions/
0013-model-artefact-deployment-and-rescore.md`.

**Not yet done, and deliberately out of scope for this update:** actually
running `prov db rescore` against the live production database. That's an
operational step against a real system, planned for immediately after this PR
is reviewed and merged (the command needs to be in the deployed image first).

## 2 — DEB-KER12 floated over blank tiles on every fresh load

**Diagnosis.** Reproduced deterministically against the live site (3/3 runs,
1920×1080 viewport, real network) - not the drawer-resize theory this
investigation started with (that one didn't reproduce under a forced regression
test; see §3). `pmtiles tile` against the deployed archive returned real vector
content for DEB-KER12's exact tile coordinates at every zoom checked, ruling out
a data-coverage gap. The browser's network log showed several pmtiles
byte-range requests aborted (`net::ERR_ABORTED`) during the map's initial
`fitBounds` ease (600ms, panning from a neutral `[0,0]` world view to the fitted
network) - MapLibre cancels in-flight tile/directory-chunk requests as the
camera keeps moving, and DEB-KER12, sitting at the fitted view's extreme eastern
edge, was consistently among the casualties. Local dev never surfaces this: a
same-origin pmtiles file resolves each range request fast enough that the churn
never outlasts the animation.

**Fix.** `mapEngine.ts`'s `fitStations` now jumps instantly (`duration: 0`) on
its first call only, tracked by a closure flag - eliminating the intermediate
camera positions that cause the request-cancellation race in the cold-load
window specifically. A later re-fit (the `stations` list changing after the
engine already has a settled view) keeps the eased pan.

**Verification status, stated plainly:** this fix could not be cleanly verified
pre-merge. It needs real GCS-backed network latency to the actual archive to
exercise the race at all - a local proxy-through-`page.route` rig was tried and
found to interfere with the app's own basemap-presence probe (a false negative,
not a real signal either way), so it was abandoned rather than trusted. The
mechanism and fix are sound by direct evidence (the archive has the data; the
requests that fetch it are being cancelled; removing the animation removes the
only thing doing the cancelling) but the very first live check after this
deploys is the real confirmation, and it will be run and reported before asking
for the next merge.

## 3 — a second, independent map bug found and fixed along the way

While investigating #2, a *different* mechanism was suspected first: MapLibre's
own internal canvas resize is a ~50ms-debounced side channel that also skips its
first callback, and the resizable station-detail drawer changes the map's flex
width live. A regression test was written to force this
(`e2e/drawer-resize.spec.ts`, dragging the handle then checking the canvas's
rendered box against its container's) - and, tested honestly, it passed even
with the fix reverted, meaning this specific interaction wasn't actually
exposing the bug in practice. It's still a real, if narrower, correctness gap
(nothing in this codebase calls `map.resize()` deterministically; the app was
relying entirely on MapLibre's own implicit behaviour), so the fix
(`MapEngine.resize()`, wired to the existing `ResizeObserver`) is kept as
low-risk hardening, and the test is kept as a real, if not bug-catching-on-its-
own, regression guard for the canvas/container invariant it asserts.

## Test gate

`make check` — **exit 0**.

    ruff check / ruff format --check   All checks passed! / 254 files formatted
    mypy                                Success: no issues found in 150 source files
    pytest                              715 passed, 2 deselected (+2 over the last update)
    Required test coverage of 88% reached. Total coverage: 90.30%
    gen_frontend_contract.py --check   Frontend contract is current.

Frontend: `pnpm typecheck` and `pnpm lint` both clean.
`e2e/drawer-resize.spec.ts` (all 4 tests, including the new one) passes locally
against a real browser.

## Deviations from the prompt

None of this was prompted as a single spec - it's the direct continuation of a
live debugging conversation. Recorded here as one update because all three
fixes landed together and share one test gate.

## Flag for review

**1. The DEB-KER12 fix is unverified against production as of this doc.** See
§2's "verification status" - this is the most important open item. Plan: the
moment this merges and deploys, re-run the same reproduction script used to
find the bug against the live URL, several times, and report the result before
treating this as closed.

**2. `provenance-tasks` (the Cloud Run Job used to train models and load data)
has no Terraform, no entry in `deploy.yml`, and predates any ADR.** ADR 0013
documents what exists but does not bring it under this repository's control.
Recommended follow-up, not done here: define it in IaC so its image tracks
`main` the way `provenance-api`'s does, instead of drifting via ad hoc `gcloud`
commands.

**3. `prov db rescore` is written and tested against the synthetic corpus, but
has not yet been run against production.** That's the very next step once this
merges - tracked in §1, not silently deferred.

**4. The drawer-resize regression test (§3) does not actually catch the bug it
names in its own description**, because that bug turned out not to be the real
one. Kept anyway as a legitimate invariant check (canvas box tracks container
box after an explicit resize), with the discrepancy stated honestly rather than
the test's intent quietly rewritten to match what it happens to prove.
