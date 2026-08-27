# Update 25 — CI runner disk, and proving Timescale independence

Date: 2026-08-28 · Branch: `update-25-ci-disk-and-timescale-independence` ·
Tag: `v1.0.26-update`

Both flags raised at the end of update 24, closed. No application code changes:
this is CI configuration, one new architecture test, and one assertion added to
an existing Docker-gated test.

## Fix 1 — the `e2e` runner ran out of disk

**What happened.** On PR #38 the `e2e` job failed twice in a row, on two
different runners, at the same point: pulling
`mcr.microsoft.com/playwright:v1.62.1-noble` for the visual-regression step.

    docker: failed to register layer:
    write /usr/lib/x86_64-linux-gnu/libgtk-4.so.1.1400.5: no space left on device
    make: *** [Makefile:123: web-visual-check] Error 125

Twice on separate runners rules out bad luck. By that point in the job the
runner has already taken uv, a project venv containing torch, the pnpm store, a
Chromium install and the loaded demo corpus; the Playwright image is roughly 2GB
more on top.

**Fix.** A `Free disk space for the Playwright image` step immediately before the
visual step (`.github/workflows/frontend.yml`), removing hosted-image toolchains
this repo never uses and pruning Docker:

    sudo rm -rf /usr/local/lib/android /usr/share/dotnet /opt/ghc \
                /usr/local/.ghcup /usr/local/share/powershell \
                /usr/share/swift || true
    docker system prune -af --volumes || true

`df -h /` is printed before and after so the margin is visible in the log rather
than guessed at. Every command is `|| true`: this step must never itself fail the
job, and a path missing from a future runner image is not an error. Android alone
is around 9GB of the roughly 25GB reclaimed.

## Fix 2 — Timescale independence is now proven, not assumed

**The gap.** ADR 0012 says the schema is portable to managed Postgres because
nothing uses Timescale. Update 24 verified the migrations no longer *reference*
it — but every place the schema actually ran used
`timescale/timescaledb-ha:pg16`, where the extension is created at initdb whether
or not anyone asks. Checked against the live local database after update 24
merged:

    extensions: plpgsql, postgis, timescaledb, timescaledb_toolkit
    hypertables: 0

Zero hypertables was the good news; `timescaledb` being present anyway was the
gap. On that image a reintroduced `create_hypertable` would work perfectly on
every developer machine and in CI, and fail only on the deployment target. The
claim was true but untested.

**Fix, in two layers.**

*The expensive half — a real engine without the extension.* CI's `e2e` `db`
service is now `postgis/postgis:16-3.5`. That job runs `prov db upgrade`,
`prov db load`, `prov audit run` and `prov graph adjudicate-db` against it, so
the whole persistence path is exercised on an engine where `create_hypertable`
does not exist. If Timescale creeps back, this job fails.

*The cheap half — a static guard in the default gate.*
`tests/architecture/test_no_timescale_dependency.py` reads every file in
`infra/alembic/versions/` and fails if any names `timescaledb`,
`create_hypertable` or `time_bucket`. No database, so it runs on every
`make check` and every PR, including on machines that have never started Docker.
It is parametrised per migration file, so the failure names the offending file,
and it carries a guard-the-guard test asserting the glob actually matched
something.

I verified it fails for the right reason rather than trusting that it passes: with
a `create_hypertable` call appended to `0002_residuals.py` it failed with
`0002_residuals.py references ['create_hypertable']`, and passed again once the
file was restored (confirmed by an empty `git diff --stat`).

*Also.* `test_migration_roundtrip.py` now asserts zero hypertables — conditionally,
since on the CI engine the `timescaledb_information` catalogue does not exist to
query. It checks `pg_extension` first and only queries the catalogue when the
extension is present, which is the local-Compose case.

**Local Compose is deliberately unchanged**, still `timescale/timescaledb-ha:pg16`.
The official `postgis/postgis` image publishes **amd64 only** — I checked the
manifests — so adopting it locally would put every Apple Silicon developer on
emulation. Multi-arch alternatives exist (`imresamu/postgis`,
`ghcr.io/baosystems/postgis`) but are personal or community namespaces, and
swapping the local database onto a third-party image to win a property that CI
already proves is a bad trade. The divergence is deliberate and is documented in
a comment on the Compose service itself, pointing at where the property is
actually tested.

## Test gate

`make check` — **exit 0**.

    .venv/bin/ruff check src tests            All checks passed!
    .venv/bin/ruff format --check src tests   254 files already formatted
    .venv/bin/mypy                            Success: no issues found in 150 source files
    .venv/bin/pytest                          713 passed, 2 deselected
    Required test coverage of 88% reached. Total coverage: 90.49%
    gen_frontend_contract.py --check          Frontend contract is current.

713 passed, up from 709: the four new architecture tests. Coverage is unmoved,
as expected — the new test exercises no `src/` code.

The two Docker-gated changes (the CI image and the round-trip assertion) are not
covered by the local gate; they are verified by CI on this PR.

## Flag for review

**1. `postgis/postgis:16-3.5` is a new image dependency for CI.** It is the
official PostGIS organisation image, but it is new to this repo and pinned only
to a minor version — `16-3.5` will drift as they publish patch rebuilds. If you
want CI byte-reproducible, pin the digest instead. I did not, because the rest of
the workflow pins by tag too and mixing the two conventions is worse than either.

**2. Local dev and CI now run different database images.** Documented and
deliberate, but it is a real divergence and worth knowing about: something that
works locally can now fail in CI specifically on Timescale usage. That is the
intended direction (CI stricter than local), and the architecture test catches
the common case before either runs — but it is the kind of thing that is
irritating to debug if you have forgotten it exists.

**3. The disk-space step is tuned to today's hosted runner image.** The paths it
removes are the ones GitHub currently ships. When they change the image, the
`rm` calls silently no-op — by design, but it means this fix can quietly stop
working. The `df -h` output before and after is the early warning; if the "after"
figure starts looking tight, that is the signal.

**4. `ci.yml` still has no database service, so `test_migration_roundtrip.py`
never runs in CI.** The round-trip assertion added here therefore only runs when
someone runs it locally with Docker up. The e2e job covers the same migrations
in a more end-to-end way, which is why I did not add a Postgres service to
`ci.yml` — but "the round-trip test is covered by CI" would be false, and worth
saying plainly.
