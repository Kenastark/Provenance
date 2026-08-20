# Update 4 — basemap diagnosis and polish

Branch: `update-4-basemap`. Tag: `v1.0.5-update`.

## Diagnosis: (a) or (b)?

Neither, cleanly. `apps/web/public/basemap/debrecen.pmtiles` was already present
(6,341,244 bytes, valid `PMTiles` magic) from an earlier fetch, so this was not
case (a). `make basemap` was re-run for the record anyway: idempotent no-op in
0.06s when the file exists; a genuine fresh fetch (file removed first) succeeded
in 10.95s wall time (10.06s inside the `pmtiles extract` CLI) for a 6,349,654-byte
archive. The SPA-fallback trap from ADR 0006 was checked directly — `curl -H
"Range: bytes=0-6"` against the dev server returns a real `206 Partial Content`
with the `PMTiles` magic, not `index.html` — so `probeBasemap` was not the fault
either.

The actual fault, found by driving the dev server in a real Playwright-controlled
browser and tracing `containerRef`'s call sequence: `useMapEngine.ts` carried a
redundant `useEffect(() => () => engineRef.current?.destroy(), [])` alongside the
callback ref that already handles teardown (destroy-then-null when called with a
new node or `null`). React 18 StrictMode — on by default in `main.tsx` — double-
invokes an effect's cleanup once in development, as if simulating an unmount and
remount. That cleanup ran once, right after the ref had just created the engine,
and destroyed it; nothing recreated it, because the ref callback itself is not
subject to that double-invoke and was never called again. The map was left with
no canvas, stuck on `data-map-state="moving"` forever — bare marker dots over
whatever background colour the container div carried, exactly the reported
symptom. This only manifests in `pnpm dev` (StrictMode is stripped from
production builds), which is why the Playwright suite — which builds and
previews — never caught it. Fixed by deleting the redundant effect; the callback
ref was always the correct, sole owner of teardown.

## What was built

1. **The StrictMode/teardown fix** above (`useMapEngine.ts`).
2. **A second, independent bug found while verifying re-theming**: the token-
   ground fallback (no fetched tiles) never re-painted on a dark/light switch.
   Root cause: `ThemeProvider` (`lib/theme.tsx`) set `data-theme` from a plain
   `useEffect`. React fires passive effects child-before-parent within a commit,
   so `useMapEngine`'s style-reapply effect (a descendant) always ran *before*
   the ancestor `ThemeProvider`'s effect had written the new attribute, and read
   the stale CSS custom property. Switched that one effect to `useLayoutEffect`:
   all layout effects across the tree complete before any passive effect starts,
   so the attribute is correct by the time the map reads it. Confirmed against a
   real streets basemap too (already worked there, unaffected either way, but
   verified it still holds after the fix).
3. **Station-id labels** beside each marker (`STA-01` etc.), token-styled
   (`prov-panel`, `text-micro`, `font-mono`), offset via `left-full ml-1` so they
   never sit on top of the marker glyph. Collision handling is geometry, not a
   guessed zoom cutoff: `visibleStationLabels` (`stationMarkers.ts`) projects
   every marker, estimates each label's screen-space box from its actual text
   length, and greedily keeps a label only if its box doesn't intersect one
   already placed — processed in station-id order for a deterministic result
   independent of array order. This naturally re-densifies on zoom-in and
   declutters on zoom-out without a magic-number threshold; verified against the
   real 18-station demo corpus (STA-01/STA-02 share a latitude and sit 18px
   apart under the map's own projection — exactly the case the function exists
   for). Labels are `aria-hidden` — the marker button's accessible name already
   carries the station id.
4. **Two basemap notices, not one.** `useMapEngine` now returns `tilesPresent:
   boolean | null` (tri-state: unresolved / confirmed absent / confirmed
   present) alongside the existing `basemapAvailable` (whether MapLibre could
   construct at all). `NetworkMap.tsx` renders `basemap-unavailable-engine`
   ("Basemap unavailable in this browser…", a browser/environment problem) only
   when `!basemapAvailable`, and a new `basemap-unavailable-tiles` ("Street
   basemap not fetched… Run `make basemap`…", a `make basemap` problem) only
   when the engine is fine but the probe has confirmed no archive. The tri-state
   avoids a false-positive flash of the tiles notice during the probe's network
   round trip. Both notices are capped `max-w-xs` so the centred banner clears
   the wind readout at the demo viewport — verified by pixel-diffing a captured
   screenshot against the two panels' measured `boundingClientRect`s after an
   earlier pass showed genuine overlap.
5. **Attribution**: confirmed rendering, not just carried — `© OpenStreetMap` is
   visible in the map's bottom-right corner in every basemap screenshot taken
   during this update, both themes, both the streets and (n/a, attribution is
   basemap-only) token-ground states.

## Test gate

- `make check` (ruff, ruff format, mypy strict, pytest, contract-drift check):
  green. 651 passed, 90.51% coverage (floor 88%). Frontend contract current.
- `make web-lint` (eslint + `tsc --noEmit`): green, no findings.
- `make web-test` (vitest + coverage): green, 217 passed (208 pre-existing + 9
  new — `visibleStationLabels` collision/offset/determinism, the two-notice
  distinction with a stubbed `fetch`, and the labelled-marker/aria-hidden case).
- Visual baselines regenerated on both platforms and verified green
  (`--update-snapshots=all` on darwin — see deviation below re. the default
  `--update-snapshots` mode; `make web-visual-linux` in the pinned
  `mcr.microsoft.com/playwright:v1.62.1-noble` container), then
  `make web-visual-check` / a plain `npx playwright test` re-run, both green.
  Only the 4 `map-*` files changed on each platform (8 total) — `station-detail-*`
  and `timeline-*` are untouched once a model-artefact contamination in the
  local API state (below) was cleared, matching this task's own map-only scope.
  `public/basemap/debrecen.pmtiles` was moved aside for every capture and
  restored after — ADR 0006's rule holds: the visual gate tests the token
  ground, never the fetched streets.

## Deviations from the prompt

- **`--update-snapshots` (no explicit mode) silently kept a stale baseline.**
  Playwright 1.62's default update mode is `changed`, which uses a looser
  similarity check than the `toHaveScreenshot` pass/fail threshold to decide
  whether a snapshot is worth rewriting. A measured, genuine 1.19%-of-pixels
  diff (well over the repo's 0.2% gate) between the old wide notice and the new
  narrow one was judged "not changed enough" three separate runs in a row and
  never got written — caught by overlaying the measured `boundingClientRect`
  values on the saved PNG and finding they didn't match what was actually
  rendered. `--update-snapshots=all` forces an unconditional rewrite and was
  used for every regeneration pass after that, on both platforms.
- **Found and fixed a second, undocumented bug** (the `ThemeProvider` effect-
  ordering one, item 2 above) that isn't named anywhere in the prompt. It was
  invisible in every previously-committed baseline because those had been
  captured with the fetched basemap still present (streets, not the token
  ground the visual gate is supposed to test) — see the next point — so the
  token-ground re-theme path had never actually been exercised by the gate
  before. Fixed rather than left, since "make sure the basemap re-themes
  correctly" is explicit in the prompt and this is the default (no-tiles) case
  every fresh clone and CI run is in.
- **The previously-committed `map-*` baselines were themselves non-compliant
  with ADR 0006**: they showed real Debrecen streets, not the token ground,
  because whoever last regenerated the darwin set did not move
  `public/basemap` aside first (the Linux container path does this
  automatically; the darwin/native path does not, and never has — nothing
  enforces it). Not this update's bug to leave in place: recaptured all `map-*`
  baselines, both platforms, both themes, with the fetched archive absent, per
  ADR 0006's stated intent.
- **The local API had trained model artefacts on disk from earlier session
  work** (the exact contamination `u2-nav-spacing.md` and `u3-resizable-panel.md`
  already recorded), so the first `station-detail-*` capture pass came out
  live-model (no "Degraded mode" banner, an extra "Parameters" section with
  sparklines) instead of the pinned degraded state `make demo-data` alone
  documents. Caught the same way those two reports describe: the diff was far
  larger than anything this update's code could plausibly cause, since nothing
  here touches the station detail panel. Restarted the local API with
  `PROVENANCE_ARTEFACTS_DIR` pointed at an empty scratch directory (no artefacts
  moved or deleted) and recaptured; `station-detail-*` came back byte-identical
  to the already-committed baseline on darwin and correctly degraded on Linux,
  confirming those files needed no change at all for this update.
- Not requested, but necessary to make the "no tiles" notice legible: capped
  both basemap notices at `max-w-xs` so the centred banner stops overlapping
  the wind readout panel at the demo viewport (1440×900). Without it, the new
  tiles-absent notice — which the prompt explicitly asks to add — would ship
  unreadable on the one screen size the visual gate and the actual demo both
  use.

## Flag for review

- The label-collision function's box-size estimate (`stationId.length * 6px +
  8px`, 14px tall) is a heuristic tuned to the current `text-micro`/`font-mono`
  pairing at the current zoom's marker size, not a measured DOM value — it errs
  slightly conservative on purpose (better to hide a label that would have just
  fit than to let two overlap). If the marker size, font, or label offset ever
  change, this constant should move with them; nothing enforces that link today.
- `docs/decisions/0006-fetched-local-basemap.md`'s own text says the container
  build "drops `public/basemap` before screenshotting" as if this were a
  general property of the visual gate — it is specific to the Linux container
  path in the Makefile. The darwin path has no equivalent safeguard, which is
  exactly how the pre-existing `map-*` baselines ended up showing streets. A
  follow-up worth doing: add the same guard (or a pre-flight check that fails
  loudly if `public/basemap` exists) to the darwin capture command itself,
  rather than relying on whoever runs it to remember.
