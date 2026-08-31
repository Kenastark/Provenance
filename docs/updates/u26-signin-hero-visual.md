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
  an unverified Layer 1 station reading, the Layer 2 engine's mini graph, and
  a Trust Score radial dial — joined by a dashed then solid connector,
  reproducing the three-panel layout of the supplied reference image. Every
  colour is a `var(--prov-*)` token (amber for "unverified", Trust Blue for
  the engine's own chrome, Sentinel Green for what it verifies), so
  `no-inline-hex.test.ts` passes unchanged. `aria-hidden="true"`: the 180
  µg/m³ reading, the 98.4% score, and "ENV-PLUME-PASS" are a worked example
  for the graphic, not a claim wired to any real station.
- **`styles/base.css`**: three small `@keyframes` (`prov-pulse`,
  `prov-edge-glow`, `prov-connector-flow`) for the pulsing indicator dot, the
  glowing graph edges, and the flowing dashed connector — covered by the
  existing global `prefers-reduced-motion` override, no new guard needed.
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

- **The hero visual's numbers (180 µg/m³, 98.4%, "Station #04",
  "ENV-PLUME-PASS") are illustrative, not derived from a dataset.** Standing
  rule 1 is about numbers that *should* come from data — a defect rate, a
  completeness figure, a trust score presented as real. This is a
  decorative marketing graphic explaining a concept, in the same register as
  the reference image itself, not a report. But [[u15-signin-screen]]'s own
  commit message called out "no stats are hardcoded in the copy per standing
  rule 1" as a deliberate choice for this exact screen, so it's worth the
  user's explicit sign-off that a worked-example graphic is a different case
  than copy stating a number as fact — rather than something assumed on this
  end.
- E2E/visual baselines genuinely not run — see Test gate above. Do not treat
  this update as merge-ready until that gate runs and passes, in addition to
  design approval.
