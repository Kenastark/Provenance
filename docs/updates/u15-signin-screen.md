# Update 15 — sign-in screen

Branch: `update-15-signin-screen`. Tag: `v1.0.16-update`.

## What was built

A sign-in screen now sits in front of the dashboard, using the exact same
mechanism the account menu's dev role switcher already used — `lib/role.tsx`'s
`setRole`/`canSwitch` — rather than any new authentication:

- **`lib/role.tsx`**: `RoleProvider` gained `signedIn`, `signIn`, and `signOut`.
  `signedIn` starts `false` unless `provenance.role` is already in
  `localStorage`; when `canSwitch` is `false` (a real deployment with a pinned
  `VITE_API_KEY`), an effect calls `signIn(role)` on its own right after mount,
  since there is nothing to choose. Also exported `keyToRole` (unchanged, now
  public), and added `roleGrants`/`ROLE_HIERARCHY` so the sign-in screen and
  `RbacMatrix.tsx` share one "what does this role grant" sentence instead of
  each computing it inline — `RbacMatrix.tsx` was refactored to use these
  rather than its own duplicate.
- **`features/shell/SignInScreen.tsx`**: the centred lockup (96px, larger than
  the top bar's 56px), the descriptor sentence taken verbatim from
  `CLAUDE.md`/`README.md` ("AI Trust Layer for Environmental Data" — not the
  "Is This Real?" demo hook, per `TopBar.tsx`'s own comment on that
  distinction), four role cards when `canSwitch` is true (each showing
  `ROLE_LABELS` and `roleGrants`), a "paste an API key" field that resolves the
  typed string through `keyToRole` and signs in on a match, and a caption
  adapted from the account menu's own sentence. When `canSwitch` is false it
  shows a non-interactive "Signed in as {role}" line instead of the four
  cards, which the provider's own effect immediately carries past.
- **`features/shell/SignInGate.tsx`**: renders `SignInScreen` in place of
  `children` while `!signedIn`; moves focus to `#main` on the transition into
  the dashboard (not on an already-signed-in initial load). Wired into
  `App.tsx` around `<AppRoutes />`.
- **`TopBar.tsx`**: a "Sign out" button next to the existing dev role
  switcher, calling `signOut()`.
- Untouched, as instructed: `RequireRole`, `require(Role.X)` in
  `api/auth.py`, and everything else in the access boundary.

## Test gate

**Unit** (`pnpm test:coverage`): 286 passed (25 files), including a new
`SignIn.test.tsx` (10 tests) covering the gate showing/skipping the sign-in
screen, role-card selection, the pasted-key path (accept and reject), the
`canSwitch: false` path never rendering the four-card picker, focus landing on
`#main` after sign-in, full keyboard reachability, and sign-out returning to
the sign-in screen. Coverage 94.97% lines / 85.18% branches / 84.73% functions
(gate is 80%). `pnpm lint` and `pnpm typecheck` clean.

**Backend** (`make check`, unaffected by this frontend-only change but rerun
for the record): 683 passed, 2 deselected, 90.63% coverage (gate 88%).
`make web-contract-check`: current, no drift.

**e2e** (`pnpm exec playwright test`, real API + real 18-station demo corpus,
`--project=chromium` and `mobile`): all 64 functional/accessibility tests
green — `accessibility.spec.ts` (25, including 4 new for the sign-in screen:
no critical violations dark/light, full keyboard reachability with a visible
focus ring, focus landing on `#main`), `demo-path.spec.ts` (17),
`drawer-resize.spec.ts` (3), `signoff-flow.spec.ts` (3), `responsive.spec.ts`
(15, both projects), and the new `signin-flow.spec.ts` (1: choosing a role
lands on the network map, survives a reload, sign-out returns to sign-in).

**Visual baselines**: 14/14 on both platforms.
- **New** (the sign-in screen didn't exist before): `signin-dark` and
  `signin-light`, `-chromium-darwin.png` and `-chromium-linux.png` (4 files).
- **Re-captured for the seeding change alone**: `global-setup.ts` now seeds
  `provenance.role` into storage for every existing spec (see Deviations), so
  all twelve pre-existing screens were re-verified end to end. On Linux (the
  CI-authoritative set) all twelve matched the existing committed baselines
  byte-for-byte — no pixel changed. On darwin, `map-{dark,light}`,
  `station-detail-light`, and `admin-{dark,light}` likewise matched exactly;
  `alert-centre-{dark,light}`, `quality-monitor-{dark,light}`,
  `station-detail-dark`, and `timeline-{dark,light}` (7 files) came back with
  a small pixel diff and were re-committed — consistent with the project's own
  documented darwin-only drift precedent
  ([[e2e-visual-baselines-gotcha]]), not a regression (confirmed by the
  Linux set matching exactly against the identical fresh corpus).

Regenerated per [[e2e-visual-baselines-gotcha]]: `docker compose down -v` →
`make up` → `make demo-data` (fresh 18-station corpus, confirmed via
`/v1/stations`) → local trained model artefacts moved aside → darwin via
`pnpm exec playwright test e2e/visual.spec.ts --update-snapshots` → Linux via
`make web-visual-linux VISUAL_API_URL=http://host.docker.internal:8000` (API
rebound to `0.0.0.0`) → artefacts restored last.

## Deviations from the prompt

- **Playwright storage-state seeding used `globalSetup` + `use.storageState`
  rather than a per-spec `beforeEach`.** One `page.goto("/")` + one
  `localStorage.setItem` in a Playwright-launched browser, saved to
  `e2e/.auth/operator-state.json` (gitignored) and applied to every project via
  `use.storageState`; the two sign-in-screen specs opt back out with
  `test.use({ storageState: { cookies: [], origins: [] } })`. Same effect as a
  `beforeEach`, chosen because it seeds once per run instead of once per test.
- **`RequireRole` was not touched** (as instructed) but note for the record:
  it still reads `useRole()` directly, which is now always inside
  `SignInGate` at runtime, so nothing in this update changed its behaviour —
  confirmed by `App.test.tsx`'s existing `AppRoutes`-only tests passing
  unchanged (they render `AppRoutes` directly, below where the gate sits, so
  they never see it — intentional, not an oversight).

## Flag for review

- **This update's actual code took under an hour; verifying the e2e/visual
  gate took most of a session.** The local machine (8GB RAM) could not sustain
  the full Playwright suite (build + preview + real Chromium + the API) for
  its ~20-minute duration without something dying partway through — first the
  standalone `uvicorn` process (apparent memory pressure), then, after the
  user closed other apps to free RAM, Docker Desktop itself came down and took
  Postgres/Redis with it (surfaced as "connection to server ... Connection
  refused" in the API log, not as any application bug). Diagnosed by batching
  the suite into small per-test chunks with an API health-check/restart before
  each, which converged to a stable failing set whose error signatures (DB
  connection refused, then a map that never left `data-map-state="moving"`)
  pointed at the real cause rather than at the sign-in gate. Once Docker was
  restarted and the corpus reloaded fresh, the entire suite passed cleanly and
  quickly (2.3 minutes for all 64 functional/a11y tests, well under a minute
  each for both visual baseline sets) — nothing here was actually flaky at the
  application level. Worth a note for whoever runs the next update on this
  machine: check `docker ps` and free memory before trusting a red e2e run.
- **`roleGrants`/`ROLE_HIERARCHY` is a small refactor beyond the prompt's
  explicit ask**, done because the prompt itself said to reuse
  `RbacMatrix.tsx`'s hierarchy wording rather than write a second copy, and
  the two were duplicating a private constant before this update.
