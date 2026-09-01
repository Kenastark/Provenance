# Update 27 — fetch the basemap and fonts in the production deploy

Date: 2026-09-01 · Branch: `update-27-basemap-fonts-in-prod-deploy` ·
Tag: `v1.0.28-update`

## STEP 0 — verify current state (diagnostic, no changes)

Commit `ce0edc2` ("fix: allow the production frontend origin through the API's
CORS gate (#45)") is on `main` — confirmed with
`git merge-base --is-ancestor ce0edc2 main`.

`deploy.yml` has run against it and succeeded:

    completed  success  fix: allow the production frontend origin ...  Deploy  main  push  33492955121  13m58s

`www.provenancel2.com`'s Network map tab loads station data now. Checked
directly against the live API rather than assumed:

    curl -X OPTIONS https://api.provenancel2.com/v1/stations \
      -H "Origin: https://www.provenancel2.com" \
      -H "Access-Control-Request-Method: GET" \
      -H "Access-Control-Request-Headers: X-API-Key"
    → access-control-allow-origin: https://www.provenancel2.com

    curl https://api.provenancel2.com/v1/stations \
      -H "Origin: https://www.provenancel2.com" -H "X-API-Key: prov-public-key"
    → HTTP/2 200, access-control-allow-origin: https://www.provenancel2.com

Both preflight and the real request now carry the production origin in
`Access-Control-Allow-Origin`. #45 is fully effective; nothing from that fix
needed redoing here.

## STEP 1 — the map still shows the token ground, not real streets

**The gap.** `apps/web/public/basemap/` and `apps/web/public/fonts/` are
gitignored by design (ADR 0006, ADR 0011): a developer runs `make basemap` and
`make fonts` once, locally, and the dashboard renders real Debrecen streets
under the markers from then on. Neither has ever run in CI. `deploy-web` in
`.github/workflows/deploy.yml` does a fresh `actions/checkout` and `pnpm build`
straight from that checkout, so `dist/basemap/` and `dist/fonts/` have always
shipped empty. `probeBasemap()` in `mapStyle.ts` reads this correctly and falls
back to the token-coloured ground — the fallback is working exactly as
designed, it has simply never been handed the files to find. This is a gap
distinct from #45: #45 fixed *whether the map's data loads at all* (station
markers); this fixes *what the map looks like underneath them* (streets vs.
plain ground).

**Fix.** One new step in the `deploy-web` job, between `pnpm install` and
`pnpm build`:

```yaml
- name: Fetch the real-streets basemap and label fonts (best-effort, ADR 0006/0011)
  run: |
    make basemap || echo "basemap: skipped — falling back to token ground"
    make fonts || echo "fonts: skipped — streets will show without labels"
```

Mirrors exactly how `make demo` already treats these two targets (Makefile,
`demo:`) — non-fatal, because a transient failure to reach
`build.protomaps.com` or the Protomaps assets host must never break a deploy,
it only costs the streets (or their labels). `deploy-api` and the
`PROVENANCE_CORS_ORIGINS` block from #45 are untouched — confirmed by
`git diff --stat`, only `.github/workflows/deploy.yml` changed, and only this
one hunk in it.

Nothing is committed under `apps/web/public/basemap/` or `apps/web/public/fonts/`
— both stay gitignored (rule 10). The fetch runs fresh on every deploy.

## Visual-baseline impact — checked, not assumed

The task instructions asked me to confirm rather than assume that this has no
effect on the Playwright visual-regression baselines. Two independent reasons
it doesn't:

1. `deploy.yml` and `.github/workflows/frontend.yml` (which runs the visual
   gate) are separate workflows with separate checkouts and separate jobs —
   nothing in one is visible to the other.
2. Even so, the visual gate strips these directories itself. Reading
   `run_visual_in_container` in the `Makefile` (used by both
   `web-visual-check` and `web-visual-linux`):

       rm -rf /build/public/basemap /build/public/fonts;

   This runs unconditionally, on every invocation, before Playwright ever
   starts. So even a checkout that already had the basemap fetched would have
   it removed before a single screenshot is taken.

ADR 0006's claim ("the visual gate deliberately drops the basemap and tests
the token ground") is still accurate. No baselines were touched.

## Test gate

`make check` — **exit 0**.

    ruff check / ruff format --check   All checks passed! / already formatted
    mypy                                Success: no issues found
    pytest                              713 passed, 2 deselected
    Required test coverage of 88% reached. Total coverage: 90.48%
    gen_frontend_contract.py --check   Frontend contract is current.
    pnpm gen:types && git diff --exit-code -- src/api/schema.d.ts   clean

Only `.github/workflows/deploy.yml` changed, so `web-lint`/`web-test` were not
required per the task instructions and were not run.

## Deviations from the prompt

None. The step was added in the exact location and with the exact non-fatal
contract specified.

## Flag for review

**1. This adds real wall-clock time and one more external-network dependency
to every production deploy.** `make basemap` downloads a `go-pmtiles` CLI,
probes up to 14 days of Protomaps daily planet builds, then extracts the
Debrecen bounding box (~10 MB) from a remote `.pmtiles` file over HTTP range
requests; `make fonts` pulls three font weights from a GitHub Pages host. Both
are non-fatal and idempotent, but a slow or unreachable host now adds minutes
to `deploy-web` rather than failing it outright. If deploy latency becomes a
concern, the alternative is fetching once and caching the artefacts (e.g. in
GCS) rather than re-fetching from the public hosts on every push to `main` —
not done here since the task asked specifically for the two `make` calls,
non-fatal, matching `make demo`'s existing contract.

**2. The production basemap will now silently drift with the upstream daily
planet build.** `fetch-basemap.sh` always takes the most recent build within
its 14-day lookback, so two consecutive deploys can extract from different
upstream snapshots. This is the same non-determinism ADR 0006 already accepted
for local `make basemap` runs; it simply now also applies to the deployed
site. Not a regression this update introduces, but worth naming since it's now
live rather than developer-local.

**3. #45's fix is confirmed working end-to-end from the live API, not just
from the deploy log.** Included the curl output above rather than trusting
"the workflow went green" as proof — a passing CI run is not the same claim
as "the production behaviour is correct," and this project's docs have
carried unverified verdicts before.
