# Update 3 — resizable station detail panel

Branch: `update-3-resizable-panel`. Tag: `v1.0.4-update`.

## What was built

`--prov-drawer-width` moves 380px → **520px**, measured rather than guessed: a
Playwright script rendered `StationDetailPanel` against the longest realistic
content (a full 4-component trust breakdown, 5 reason codes, 7 parameter rows,
the "Show all" state expanded) and swept the token value to find the smallest
width at which nothing overflows. The actual driver of the reported bug is the
`<table>` in `TrustBreakdown.tsx`: it carries no width constraint, so the browser's
automatic table-layout algorithm sizes it to its content's preferred width (499px
of table content at the viewport measured, ~516px including the panel's padding
and border) regardless of the container — that is what was clipping the
Value/Weight/Contribution columns, not the sparkline. 520px leaves a few px of
headroom for the font-metric differences between the macOS and Linux baseline
environments.

The panel's left edge now carries a drag handle (`DrawerResizeHandle.tsx`): an
ARIA "window splitter" (`role="separator"`, `aria-orientation="vertical"`,
`aria-valuenow/min/max`, focusable, arrow-key and Home/End keyboard operation,
double-click reset), wired through a new `lib/drawerWidth.ts` that clamps to
`[360px, 60% of the viewport]`, persists the chosen width to `localStorage`
(`provenance.drawer-width`), and restores it on load. The default width itself is
read from the `--prov-drawer-width` token at runtime rather than duplicated as a
literal, so a future token edit and "reset to default" both stay correct without
touching this file. The handle is rendered in both the loaded and the
empty-state panel, `lg`-only (the drawer is stacked full-width below that
breakpoint, where a pixel width is meaningless).

`Sparkline` gained a `fluid` prop: when set, the SVG's CSS width is `100%` of its
container instead of the fixed pixel `width` prop, so the trust-trajectory chart
scales with the panel rather than becoming a second overflow source at a
narrower dragged width. Only the trust-trajectory instance uses it; the small
per-parameter sparklines beside their row labels are unaffected.

## Test gate

- `make check` (ruff, ruff format, mypy strict, pytest, contract-drift check):
  green. 651 passed, 90.60% coverage (floor 88%). Frontend contract current.
- `make web-lint` (eslint + `tsc --noEmit`): green, no findings.
- `make web-test` (vitest + coverage): green. 210 passed (204 pre-existing + 6
  new: `drawerWidth.test.ts` covers the clamping logic — min/max floor and
  ceiling, the 60%-of-viewport cap never dropping below the 360px floor — and
  the persistence round-trip — write/read, corrupt-value recovery, clear;
  `DrawerResizeHandle.test.tsx` covers the ARIA attributes, arrow-key and
  Home/End keyboard resizing, and double-click reset).
- `apps/web/e2e/drawer-resize.spec.ts` (new, 3 cases, all green): dragging the
  handle widens the panel and shrinks the map region by the same amount (their
  combined width is conserved to within a few px, the handle's own width);
  the width survives a page reload; double-click resets to the token default and
  clears `localStorage`; the handle is keyboard-focusable, carries the correct
  ARIA separator attributes and an accessible name, and arrow keys resize it.
- `apps/web/e2e/accessibility.spec.ts`: green, all 16 cases, unchanged.
- `apps/web/e2e/responsive.spec.ts` (mobile project, 390px): green, all 7 cases —
  confirms the handle does not appear or affect layout below `lg`.
- `apps/web/e2e/demo-path.spec.ts`: green, all 12 cases.
- Visual baselines regenerated on both platforms
  (`pnpm exec playwright test --project=chromium e2e/visual.spec.ts --update-snapshots`
  on darwin, `make web-visual-linux` in the pinned
  `mcr.microsoft.com/playwright:v1.62.1-noble` container), then verified green
  with `make web-visual-check`. 12 of 16 files changed: `map-*`,
  `station-detail-*`, and `quality-monitor-*`, both themes, both platforms.
  `timeline-*` is untouched — that screen never renders the drawer. The map and
  quality-monitor screenshots move because the resize handle now occupies a few
  px even in the empty (no station selected) panel, narrowing their neighbouring
  `flex-1` region by the same amount.

## Deviations from the prompt

- **Restarted the local API against an empty `PROVENANCE_ARTEFACTS_DIR` before
  the real capture pass**, the same contamination this repo's own
  `docs/updates/u2-nav-spacing.md` already recorded. The first baseline pass was
  captured against a local API that still had phase-5 model artefacts on disk
  from earlier session work, so `station-detail-*` came out in the *live-model*
  state (no "Degraded mode" banner, a populated trust-trajectory chart) rather
  than the pinned `degraded` state `make demo-data` alone is documented to leave
  the API in. Caught by diffing the freshly generated PNG against the
  previously committed one before trusting it — the previous commit's baseline
  visibly showed "Degraded mode — statistics layer only" and the reported
  cut-off table (only "Value" was visible; "Weight" and "Contribution" were
  clipped entirely), which the contaminated capture did not reproduce. Reverted
  the contaminated baselines with `git checkout --`, restarted the API pointed
  at a scratch artefacts directory, and recaptured; the correct pinned state
  reproduced the original bug exactly, then showed it fixed.
- **Used a temporary, unpicked-up Playwright script (`page.route`-mocked API,
  full 4-component/7-parameter fixture) to do the width measurement**, rather
  than eyeballing a number or measuring against a partial fixture. Deleted
  before the final commit — it exists only in this report, not in the tree.
- The prompt suggested the sparkline might be part of the overflow; measurement
  showed it was not (320px fit comfortably inside the panel at every width
  tested) — the table was the sole cause. Made it `fluid` anyway, since the
  prompt asked to "check whether it should follow the panel width instead of
  staying fixed" independent of whether it was the current bug's cause, and a
  fixed-320px chart would become the overflow source the moment someone drags
  the panel narrower than ~380px.

## Flag for review

- The 520px default was measured once, on this machine, at the Chromium/macOS
  render used for the darwin baseline capture (1440×900 viewport). The Linux
  container's font metrics render the same content at a very slightly different
  width (confirmed by the Linux baseline capture succeeding cleanly with the
  same token value), so the few px of headroom absorbed that difference here —
  but this was not swept the way the 380px→520px threshold itself was. If a
  future content change (a longer component name, a sixth trust component)
  pushes the table's natural width past 520px again, the fix is the same
  measurement process, not a larger constant guessed in advance.
- The underlying `<table>` in `TrustBreakdown.tsx` still has no width constraint
  of its own — this update widened the drawer to fit its unconstrained natural
  width rather than making the table itself responsive (e.g. `table-layout:
  fixed` with column wrapping). That is consistent with what the prompt asked
  for and with the explicit minimum-width note ("~360px, below which the table
  breaks again"), but it means dragging the panel down to the 360px floor still
  reproduces a milder version of the original clipping. Worth a follow-up if the
  minimum width is ever lowered further.
