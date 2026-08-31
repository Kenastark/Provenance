# Update 26 — sign-in hero copy and flow visual

Branch: `signin-hero-visual`. Tag: pending — assigned at merge, once the
design is reviewed and approved.

## What was built

The sign-in screen's intro block (added in [[u15-signin-screen]]) gets new
copy and a new graphic, both requested directly against a design reference
rather than derived from data:

- **Headline**: "AI Trust Layer for Environmental Data" -> "An AI trust layer
  for Environmental Sensor Networks." — now `whitespace-nowrap` so it always
  renders on one line, at the same `text-display-l` size as before.
- **Write-up**: replaced with "Data without trust is just noise." (a short
  lead line) plus one paragraph on Layer 1/Layer 2 and the HST-GAT model. The
  container widened from `max-w-lg` (512px) to `max-w-2xl` (672px) so the
  longer copy wraps to fewer lines — the explicit ask was less vertical
  space, not less text.
- **`features/shell/HeroFlowVisual.tsx`** (new): three `prov-panel` cards —
  a Layer 1 station reading flagged unverified, the Layer 2 engine's mini
  graph, and a Trust Score radial dial — joined by a dashed then solid
  connector, reproducing the three-panel layout of the supplied reference
  image. Every colour is a `var(--prov-*)` token (amber for "unverified",
  Trust Blue for the engine's own chrome, Sentinel Green for what it
  verifies), so `no-inline-hex.test.ts` passes unchanged. `aria-hidden="true"`:
  the 180 µg/m³ reading and the 98.4% score are a worked example for the
  graphic, not a claim wired to any real station — but the station id
  (`DEB-KER18`, a real land station per `station_zones.yaml`) and the reason
  code (`R22` / `PLUME_CORROBORATED`, the registry's actual GENUINE_EVENT
  verdict code) are real identifiers, per a second-pass request.
  - **Second pass, same session**: all three cards forced to an identical
    320x320px via `w-[320px] h-[320px]` (arbitrary Tailwind values) after
    discovering `w-48`/`w-52`/`w-60` — this project's Tailwind config
    replaces `theme.spacing` outright with the token scale (keys `0`-`8`
    only), so any numeric width/height class above 8 silently compiles to
    *no rule at all* and the cards had been auto-sized by content the whole
    time. Card 1's border recoloured from the default grey `prov-panel`
    border to `border-ambiguous`, matching its own amber badge, content
    centred. Card 2's graph nodes rotated 16° as a group and the centre node
    recoloured Trust Blue and enlarged (r 11 vs. the outer two's r 7),
    restoring a detail the reference image had that the first pass dropped.
    Card 3's dial enlarged (58px radius) with an SVG `<animate>` on
    `stroke-dashoffset` (full circumference -> the score's offset, 1.4s,
    spline easing) so the ring fills on mount rather than rendering
    pre-filled; guarded behind a `prefers-reduced-motion` check via
    `matchMedia` (SMIL isn't covered by the CSS-level global override the
    other animations use, so this one needed its own guard) — reduced-motion
    renders the final state directly, no animation element at all.
- **`styles/base.css`**: three small `@keyframes` (`prov-pulse`,
  `prov-edge-glow`, `prov-connector-flow`) for the pulsing indicator dot, the
  glowing graph edges, and the flowing dashed connector — covered by the
  existing global `prefers-reduced-motion` override, no new guard needed.
- **Layout bug fixed, second pass**: the outer `signin-screen` container used
  `justify-center` for vertical centring; once the hero visual made the
  block taller than most viewports, the eyebrow line and lockup — the
  content *above* the centred midpoint — became permanently unreachable.
  `overflow-y-auto` alone doesn't fix this: with `justify-content: center`,
  a browser can't scroll to the negative offset needed to reach content
  pushed above the box, only to the positive offset below it. Restructured
  to `margin: auto` on a single wrapping child instead, which centres when
  content fits and degrades to ordinary top-anchored, fully-scrollable flow
  the moment it doesn't — confirmed by scrolling the container
  programmatically end to end (`scrollTop` 0 -> 363 of a 1263px scrollHeight
  against a 900px viewport) and screenshotting both ends.
- Updated the two tests asserting the exact headline text
  (`SignIn.test.tsx`, `App.test.tsx`) and the `TopBar.tsx` comment that
  quotes it, so nothing is left pointing at the retired string.

## Test gate

**Unit** (`pnpm test:coverage`): 300 passed (26 files, up from 286/25 in
u15 — the new file plus its exercise via the existing sign-in tests).
`HeroFlowVisual.tsx` at 100% line/branch/function coverage (rendered by
every `SignInScreen` test). `pnpm lint` and `pnpm typecheck` clean.

**Manual render check**: `vite` dev server driven headlessly with Playwright
(`chromium.launch()`, not `chromium-cli` — not installed in this
environment), sign-in screen screenshotted in both themes with
`data-theme` forced via `localStorage["provenance.theme"]`. No console
errors either theme; headline on one line, write-up visibly shorter, all
three hero-visual cards legible in both palettes.

**Not run yet, deliberately**: the Playwright e2e/visual-baseline suite.
Per [[e2e-visual-baselines-gotcha]] that regeneration is expensive (fresh
`docker compose down -v`, model artefacts moved aside, both darwin and
Linux runs) and the user explicitly asked to review the design before this
goes anywhere near a PR — regenerating baselines now would be wasted work
if the visual changes further. It's the next step once the design is
approved, before merge.

## Deviations from the prompt

- **Scope kept to the sign-in screen.** The exact phrase "AI Trust Layer for
  Environmental Data" is also the canonical "Product descriptor" defined in
  `CLAUDE.md`/`README.md` and reused verbatim across `docs/demo/*`,
  `ops/demo.py`'s title-card tagline, and (per [[u15-signin-screen]]) was
  originally copied from those sources on purpose. The request read as
  scoped to this screen's UI, not a rebrand of the canonical descriptor
  everywhere it's quoted, so those files were left untouched. Flagging this
  divergence explicitly since a prior update tied them together
  deliberately — worth a call on whether the canonical descriptor should
  follow suit.
- **Amber, not red, for the "unverified spike" indicator.** The reference
  image mixed red and amber for that badge; `tokens.css` defines amber
  specifically as "anomaly, ambiguity" and red as "faults only, never a
  large field" — an unconfirmed reading is definitionally the ambiguous
  case, not yet a confirmed fault, so `--prov-state-ambiguous` was used
  throughout rather than red.

## Flag for review

- **The hero visual's reading and score (180 µg/m³, 98.4%) are illustrative,
  not derived from a dataset**, though the second pass swapped the two
  identifiers that used to be invented (a made-up "Station #04" and
  "ENV-PLUME-PASS") for real ones (`DEB-KER18`, `R22`/`PLUME_CORROBORATED`).
  Standing rule 1 is about numbers that *should* come from data — a defect
  rate, a completeness figure, a trust score presented as real. This is a
  decorative marketing graphic explaining a concept, in the same register as
  the reference image itself, not a report. But [[u15-signin-screen]]'s own
  commit message called out "no stats are hardcoded in the copy per standing
  rule 1" as a deliberate choice for this exact screen, so it's worth the
  user's explicit sign-off that a worked-example graphic is a different case
  than copy stating a number as fact — rather than something assumed on this
  end.
- **This session found a real, pre-existing gap in the Tailwind config**: any
  class needing a numeric spacing key above 8 (`w-48`, `h-64`, `w-96`, etc.)
  compiles to nothing, because `tailwind.config.ts` replaces `theme.spacing`
  wholesale with the design-token scale (`0`-`8` only) rather than extending
  it. That's exactly why the three cards came out different sizes in the
  first pass. It's very likely present elsewhere in the app too (e.g. the
  role-picker buttons still use `w-52`, `prov-input` still uses `w-64`,
  neither touched by this update) — worth its own audit and fix, out of
  scope here since this update only had to fix its own three cards.
- E2E/visual baselines genuinely not run — see Test gate above. Do not treat
  this update as merge-ready until that gate runs and passes, in addition to
  design approval.
