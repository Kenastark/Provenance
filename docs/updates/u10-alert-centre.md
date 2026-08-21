# Update 10 — Alert Centre and Admin, the phase-7 frontend

Branch: `update-9-alert-centre`. Tag: `v1.0.11-update`.

Per the working agreement for these update reports: what follows is copy-pasted or
directly quoted from a real command's output, not retyped or rounded by hand beyond
what the tool itself already rounded.

## What was built

Phase 7 shipped the operational layer — the maintenance queue, the risk-ranked
Alert Centre, the sign-off gate, RBAC, the admin surface — at the API and CLI only.
None of it rendered in `apps/web`. This update builds the two screens that make it
visible, so the product's strongest ethical claim (no public alert without a
recorded human sign-off) can be shown on stage rather than only described.

**`/alerts` — Alert Centre.** A DataTable of candidate alerts sorted by `risk`
descending, with Severity, Verdict, Exposure, Confidence, and Risk as separate
columns — so a high-exposure, low-confidence event is visibly outranked above a
confident low-exposure fault, not just true in the sort order. Selecting a row opens
a detail pane: the risk factor breakdown (`FactorBreakdown`, a new component
modelled on `TrustBreakdown` for the "never a bare number" pattern applied to
`risk_factors`/`priority`), the full adjudication case reused verbatim from the
Events screen (`AdjudicationDetail`, `parseAdjudication`), the station's trust score
reused verbatim from the map and quality screens (`TrustChip`, `TrustBreakdown`),
and the sign-off/dispatch panel. Below it, the maintenance queue: a second
DataTable with its own detail pane, status filter, a "Rebuild from latest run"
action, and forward-only lifecycle transitions read directly off
`MAINTENANCE_TRANSITIONS` (open → acknowledged → {dispatched, resolved} →
resolved).

**Sign-off and dispatch.** `SignoffPanel` records a sign-off
(`POST /v1/decision/signoff`) and gates dispatch (`POST /v1/decision/dispatch`) on a
valid, unexpired one existing for the selected channel. The dispatch button is
`disabled`, not hidden, with the reason stated in a sentence
(`aria-describedby`-linked) an operator could read aloud: *"Dispatch is blocked:
there is no valid, unexpired sign-off for this event on Webhook yet."* This is a
frontend courtesy over an already-enforced boundary — `gate.dispatch` refuses to
deliver without calling `validate_signoff` first
(`tests/architecture/test_signoff_gate.py`, untouched, still the thing that makes
the claim structurally true) — so a bug in this panel can make the UI more
cautious than the server, never less.

**`/admin`.** Three sections: an access-control panel (the role hierarchy, and
which role each operational endpoint requires, with a live "reachable/blocked"
column for the signed-in role); a status panel (version, model versions, config
hashes, retraining triggers with a "request retrain" action that is honest about
recording a request rather than training inline, audit-run history, dispatch
history); and the two-plane monitor — an infra-health tile parsed from `/metrics`
(Prometheus text, the same series a Grafana stack would scrape) kept visually
separate from the model-plane drift report (`/v1/admin/model-drift`), which draws a
chart only when a series has more than one point and says "No history yet —
{the backend's own note}" otherwise, never a one-point chart implying a trend.

**Roles.** `lib/role.tsx` replaces the hardcoded "Operator" stub with the real
four-role model (`public_read | researcher | operator | admin`), mapped to the same
four documented dev keys `src/provenance/api/auth.py` falls back to. There is no
login endpoint to wire against — ADR 0010 frames the backend's own auth as
"transport, not policy" — so the account menu grew a role switcher for exactly the
four dev keys; a deployment that pins a real `VITE_API_KEY` outside those four gets
`canSwitch: false` and the switcher disappears rather than pretending to offer
roles it cannot grant. Both new routes are role-gated (`RequireRole`), and the
gate's block is stated in the same "read it aloud" register as the dispatch block.
Nav width was the open question in the prompt: seven tabs fit one line at 1440px
with room to spare (see the `admin-dark` screenshot below) — the nav's existing
`overflow-x-auto` pattern was never actually needed here, so nothing moved into a
sub-route.

## Real bugs the live-data gate caught

Every one of these was invisible to `tsc`, `eslint`, and the 266-test unit suite —
they only showed up once the screens ran against the real API and a real browser.
Recording them because catching them was the entire point of not stopping at green
unit tests.

1. **Drift values were being double-converted.** `ops/drift.py`'s
   `defect_rate_by_station` reports `unit: "percent"` with values already ×100
   (`41.51`, not `0.4151`); the frontend's first pass ran every drift value through
   `formatRateAsPercent` (which multiplies by 100), so a real 41.51% would have
   rendered as 4151%. Confirmed against the real endpoint:
   ```
   $ curl -s -H "X-API-Key: prov-admin-key" localhost:8000/v1/admin/model-drift | head -20
   "defect_rate_by_station": { "DEB-KER01": { "unit": "percent", "points": [{"value": 41.512092}, ...
   ```
   Fixed with a `formatDriftValue(value, unit)` that formats whatever the backend
   sent once and appends the unit it actually named, never assuming a scale.

2. **A maintenance ticket's backend headline can carry an unfilled
   `{placeholder}`.** A ticket aggregates every flag behind it, and they can carry
   different evidence values (four different PM2.5-over-PM10 readings, in the real
   corpus) — there is no single number for the backend to substitute, so
   `headline` can arrive literally as `"PM2.5 ({pm25}) exceeds PM10 ({pm10}), which
   is physically impossible."` Confirmed:
   ```
   $ curl -s -H "X-API-Key: prov-operator-key" localhost:8000/v1/maintenance?limit=1 | python3 -m json.tool
   "headline": "STA-01 · PM2.5 · PM2.5 ({pm25}) exceeds PM10 ({pm10}), which is physically impossible."
   ```
   The first draft rendered that string directly — a raw placeholder reaching an
   operator's screen, exactly the failure class `demo-path.spec.ts`'s "no
   unrendered template reaches an operator" check exists to catch (now extended to
   cover `/alerts` too). Fixed by routing the ticket detail through
   `ReasonCodeBadge` (the same component every other screen uses), which degrades
   an unfillable placeholder to an em dash instead of showing it raw.

3. **`w-80` and `w-24` are not valid classes in this project's Tailwind
   config** — `tailwind.config.ts`'s `theme.spacing` is fully replaced with a
   token-driven scale (`0`–`8`, `px`, `full`), not extended, so the default
   numeric scale (which is where `80`/`24` live) does not exist. Both classes
   silently generated no CSS. For `lg:w-80` on the maintenance ticket detail
   aside, that meant `w-full` won at every breakpoint — the aside claimed 100% of
   the section's width and the list column beside it collapsed to `0px`, which is
   what an operator could see as content overlap and what Playwright saw as one
   element intercepting clicks meant for another:
   ```
   listCol: { w: 0, ... }
   aside:   { w: 1374, ... }   // should have been 320
   ```
   Fixed with the project's own established convention for a size outside the
   token scale — arbitrary-value syntax (`lg:w-[320px]`, `w-[96px]`) — rather than
   a spacing-scale class that happens to not exist.

4. **`isSignoffUsable` mis-parsed the sign-off's `expires_at`.** Every backend
   timestamp is a naive-UTC string (`format.ts`'s `parseUtc` exists precisely
   because of this), but the sign-off usability check used a bare
   `new Date(record.expires_at)`, which reads it as *local* time. In any timezone
   ahead of UTC (this machine's, at the time this was caught) that silently
   misreads a still-valid, just-recorded sign-off as already expired — recorded
   sign-offs showed "expired" immediately. Fixed by routing through the same
   UTC-safe `toDate` every other timestamp in the dashboard already uses.

None of these four were caused by a stale test fixture describing the world
wrongly — the unit suite's fixtures happened to avoid all four shapes by
construction. They are the reason the gate for this update was run against the
real API and a real demo corpus rather than accepted on green unit tests alone.

A fifth issue was in the *tests*, not the product: `visual.spec.ts` and
`signoff-flow.spec.ts` used an unscoped `page.getByTestId("data-table-row").first()`
to find an alert row, but the Alert Centre and the maintenance queue below it both
render that test id from independent fetches — on a run where the maintenance
fetch settled first, `.first()` could grab a maintenance row instead. Scoped both
specs to the alert region (`demo-path.spec.ts`'s new test and the unit tests
already did this correctly; the two e2e specs did not).

## Test gate

**Python** (unaffected by this update, run to confirm): `make check` —
673 passed, coverage 90.59%, "Frontend contract is current."

**Frontend unit** (`pnpm typecheck && pnpm lint && pnpm test:coverage`):
```
Test Files  24 passed (24)
     Tests  266 passed (266)
```
Coverage (v8, global threshold 80% on all four):
```
All files  |   94.81 |    84.98 |   84.21 |   94.81
```
New test files: `AlertCentre.test.tsx` (ranking legibility, the sign-off→dispatch
flow end to end against a stubbed client, the maintenance queue's forward-only
transitions, honest empty states), `AdminDashboard.test.tsx` (RBAC reachable/blocked
per role, "no history yet" vs. a drawn chart, the retrain honesty note, the infra
panel), `role.test.tsx`, `infraMetrics.test.ts` (the `/metrics` text parser), plus
extensions to `App.test.tsx` (nav visibility per role, the role-forbidden block) and
`client.test.ts` (the new `post()` method).

**End-to-end**, against the real API and the real demo corpus (`make demo-data`,
no models trained — the pinned pre-training state):
```
71 passed   (2.6min)
```
That is the whole suite: `accessibility.spec.ts` (every route including the new
`/alerts` and the three new admin-role cases), `demo-path.spec.ts` (including the
new Alert Centre case, verifying the real risk ordering — `risks[i-1] >= risks[i]`
— against real API data, not a fixture), `drawer-resize.spec.ts`,
`responsive.spec.ts` (including `/alerts` and `/admin`), `signoff-flow.spec.ts` (the
full sign-off→dispatch walkthrough, the structural-unreachability proof, and the
per-alert form reset), and `visual.spec.ts`.

Getting to a clean 71/71 took a second pass for a reason worth recording. The
first full run had 7 failures that looked like a real, pre-existing bug: a
network-map station marker's event-glyph intercepting clicks meant for a
neighbour, blocking every test that opens the station detail drawer. It wasn't.
This machine's `provenance-db-1` container had been running for 18 hours,
carrying accumulated data from earlier sessions on top of what a single
`make demo-data` writes — denser than a fresh corpus, dense enough that markers
overlapped at the default zoom. `docker compose down -v && make up && make
demo-data` against a genuinely fresh volume reproduced nothing: all 71 tests,
including the map ones, passed outright. Every "bug" described in an earlier
draft of this section was an artefact of a contaminated local database, not a
map defect — corrected here rather than left in. The same reset also surfaced a
second artefact worth naming: `POST /v1/maintenance/rebuild`, called by hand
earlier in this session to sanity-check the endpoint, is not something
`make demo-data` calls — a truly fresh clone's maintenance queue is empty until
an operator (or a future demo-pipeline change) populates it, which the Alert
Centre already renders as an honest empty state rather than hiding the section.

**Visual baselines**, both platforms, regenerated and re-verified stable against
the fresh database (`pnpm e2e:update` on darwin; `make web-visual-linux` then
`make web-visual-check` in the pinned `mcr.microsoft.com/playwright:v1.62.1-noble`
container):
```
darwin:  71 passed (full suite, 2.6min)
linux:   12 passed (visual.spec.ts only, 1.5min) — twice locally, to confirm stability
```
New baselines: `alert-centre-{dark,light}-chromium-{darwin,linux}.png`,
`admin-{dark,light}-chromium-{darwin,linux}.png`. Changed baselines: `map-*`,
`quality-monitor-*`, and `station-detail-*` on both platforms and both themes —
partly the two added nav tabs and the account menu's dynamic role label shifting
shared chrome by a few pixels, partly the fresh (correctly smaller) demo corpus
replacing baselines that had themselves been captured against the same
contaminated database before this was caught. `timeline-*` is byte-unchanged.

CI's own `e2e` check then caught one more thing local verification could not:
`station-detail-{dark,light}-chromium-linux.png`, as generated by this ARM Mac's
emulated Docker run, differed from CI's native amd64 render by ~2% (a font-reflow
cascade, not a content bug — see "Flag for review"). Fixed by taking CI's own
`-actual.png` captures from the failed run as the baseline instead. Every other
Linux baseline this update touched or added matched CI on the first push.

## Deviations from the prompt

1. **Renumbered `v1.0.10-update` → `v1.0.11-update` and `u9-alert-centre.md` →
   `u10-alert-centre.md`.** Both identifiers named in the prompt were already
   taken — `v1.0.10-update` and `docs/updates/u9-ker11-verdict.md` belong to the
   KER11 verdict update that merged (PR #23) after this prompt was written. Used
   the next actually-available numbers rather than reusing taken ones.
2. **Hand-written response types instead of a backend `response_model` change.**
   `routers/{alerts,maintenance,decision,admin}.py` answer with `dict[str, Any]`,
   not a Pydantic model, so `schema.d.ts` cannot generate real types for these five
   responses — `apps/web/src/api/operations.ts` hand-writes them against the
   router source instead, with the gap and the drift risk stated explicitly in
   its own doc comment and in `client.ts`'s. Adding `response_model=` to those
   four routers so the generator can take over is a clean, low-risk backend
   follow-up (the dict shapes returned would not change, only their declared
   type) but is backend work the prompt scoped to the frontend; not done here.
3. **The RBAC matrix on `/admin` is hand-mirrored, not fetched.** There is no
   endpoint that serves "which role does this operational endpoint need" as data
   — `lib/rbac.ts` restates the ten operational routes' `require(Role.X)` by hand
   against the router source, cross-checked against
   `tests/integration/test_rbac_matrix.py`. Flagged in the file's own doc comment
   as something a small `/v1/admin/rbac-matrix` endpoint would fix properly.
4. **`StationDetailPanel`'s local-only Acknowledge/Dispatch queue
   (`lib/queue.ts`) was left as is.** It is now a second, weaker action surface
   next to the real sign-off/dispatch flow the Alert Centre offers for the same
   underlying events. The prompt scoped this update to building the two new
   screens and wiring roles, not to rewiring the station drawer's existing,
   tested, unrelated actions; flagged below rather than touched.
5. **The infra-health tile is a small hand-written Prometheus text parser**
   (`features/admin/infraMetrics.ts`), not a real Prometheus client — it reads
   three named series (`prov_up`, `prov_http_requests_total`,
   `prov_http_requests_in_flight`) and says so on screen ("full detail belongs [in
   Grafana]"). A real deployment's infra plane is Grafana against the same
   `/metrics` endpoint; this is the honest minimum for an admin screen to have an
   "is the service up" tile without asking an operator to open a second tool.

## Flag for review

**The maintenance queue is empty on a fresh `make demo-data`, by design, and
nothing currently fills it before a demo.** `rebuild_maintenance` only runs when
an operator calls `POST /v1/maintenance/rebuild` (or clicks "Rebuild from latest
run" on the Alert Centre) — it is not part of `make demo-data` or `make demo`.
The screen handles this honestly (an explicit empty state with the action right
there), but whoever runs the live demo should click that button once first, or
this is a one-line addition to the demo pipeline if an always-populated queue is
preferred. Deliberately not added to the Makefile here, since it weakens the
"this is a real, no-op-until-clicked action" argument the button itself makes.

**Local dev note, not a product issue:** this session's Docker Postgres volume
had 18 hours of accumulated state from earlier work before the visual gate first
ran against it, which cost real time chasing a phantom network-map bug (see
"Test gate" above) before `docker compose down -v` isolated it as environmental
contamination rather than a real defect. Worth remembering for
next time this repo's local stack has been sitting around: `make demo-data` is
idempotent-looking but not idempotent against a dirty volume, and a "the map
looks wrong" report is worth a clean `down -v && up && demo-data` before it's
worth an hour of debugging `features/map/`.

**Second local dev note:** `make web-visual-linux` run from an Apple Silicon
Mac (`--platform linux/amd64` under Docker Desktop's emulation) does not
byte-match what the same pinned image produces on CI's native amd64 runner for
`station-detail` specifically — a text-reflow difference of a few pixels in the
"Model artefacts are unavailable..." paragraph cascaded into a ~2% pixel diff
below it, small enough to be genuine font-metric variance under emulation, not
a content bug (`map-*`/`quality-monitor-*`/`admin-*`/`alert-centre-*` all
matched CI cleanly from the same emulated run). Resolved by downloading CI's own
`playwright-test-results` artifact from the failed run and committing its
`-actual.png` captures as the baseline directly (`gh run download <id> -n
playwright-test-results`) rather than trying to reproduce native rendering
under emulation. If this recurs for other screens, the same fix applies; a
native amd64 machine (or CI itself, run once with `--update-snapshots` and the
artifact downloaded) is the more direct route than iterating locally on ARM.

**The dispatch flow has now been exercised for real, twice**, against the real
`gate.dispatch` — `channels.py`'s "offline by construction" contract held both
times (no network egress, a receipt appended to the in-process outbox). Worth
noting for whoever demos this: dispatching on stage is safe to do live.

**Sign-off records are a browser-local mirror, not a query surface.** There is no
`GET` endpoint to list existing sign-offs for an event, so the sign-off panel can
only show "who, when, which channel" for sign-offs *this browser* created
(`lib/signoffs.ts`, documented there as a display convenience — `gate.dispatch`
re-validates against the database regardless, so a stale local cache can only make
the UI more cautious, never less). A second operator, or the same operator on a
different machine, would see no history even though a valid sign-off might exist
server-side. Not a security gap; possibly worth a small `GET` endpoint later if
multi-operator sign-off review becomes a real workflow.
