# Update 31 — mobile layout at full functional parity

Date: 2026-09-09 · Branch: `update-31-mobile-responsive-parity` ·
Tag: `v1.0.31-update`

The dashboard did not lay out well on a phone. The brief was explicitly *not*
"cut features for mobile": every screen, control and destination stays reachable
at 390px, and the desktop layout is byte-identical to what it was.

## What was actually wrong

`e2e/responsive.spec.ts` has asserted a 390px floor since phase 3, and it was
passing. That test only ever asked one question — *does anything escape the
viewport horizontally* — and the answer was no. A layout can pass that and still
be unusable, which is what had happened:

- **The operator chrome could not fit.** Seven nav links, the window picker, the
  freshness line, the theme switch and the account menu shared one 72px bar with
  a 56px lockup. Nothing overflowed because the bar was `flex-wrap` — it wrapped
  to three rows inside a container with a fixed 72px height, and `#root`'s
  `overflow: hidden` clipped the rest. The nav was on screen in the DOM sense and
  gone in every sense that matters.
- **Opening a station halved the map.** The detail drawer stacked *under* the map
  in the same flex column below `lg`, so the two divided one screen's height
  between them: tapping a marker scrolled away the thing you tapped.
- **The sign-in screen had never been measured at this width.** Every other spec
  starts from a pre-seeded role, so the one screen a first-time visitor sees was
  the one screen the 390px test never loaded. It carried a fixed 1120px hero row
  (three 240px cards, two 200px connectors, all `shrink-0`) and a `nowrap`
  headline at 27px — roughly three phone widths of unbreakable text, centred, so
  it lost content off *both* edges. It also pinned the theme switch at
  `right-[116px]`, a measurement taken against the 1440px desktop bar.
- **Controls were sized for a mouse.** `--prov-row-height` is 32px, and every
  button and input derives its height from it. 44px is the documented minimum tap
  target on both iOS and Android.
- **Four tables had no narrow-width story.** `TrustBreakdown` is the sharp one:
  the `--prov-drawer-width` token is 520px *because* that table overflows below
  ~516px (the token's own comment says so), and the mobile sheet is narrower than
  that floor by design.

## What changed

**Tokens carry the touch sizing.** A `@media (max-width: 1023.98px)` block at the
foot of `tokens.css` re-points `--prov-row-height` (32→44px),
`--prov-topbar-height` (72→56px) and a new `--prov-lockup-height` (56→36px). No
component knows it is on a phone; `.prov-button`, `.prov-input` and `.prov-table
td` grow because the token they already referenced changed. Sizing only — no
colour is redefined, because a theme is a theme at every width. `1023.98px`
rather than `1023px` so a fractional viewport cannot fall between this query and
Tailwind's `min-width: 1024px` and match neither.

**The chrome collapses below `xl`, as one DOM tree.** The nav, window picker,
theme switch and account menu move into a single wrapper that is a flex row in
the bar from `xl` up and a dropdown panel hanging off the bar below it. Rendering
a separate "mobile nav" would have been easier to read and wrong: every link
would exist twice, so `getByRole("link", { name: "Admin" })` starts throwing on a
duplicate match and a screen reader announces the whole chrome twice. `xl` rather
than `lg` because the bar needs roughly 1200px before those controls stop
crowding, which is well above where the map/drawer split wants to change.
Escape, a tap outside, and following a link all close it.

**The station detail is a bottom sheet.** Below `lg` it overlays the map,
capped at 70% height with the header sticky so Close never scrolls away. The map
keeps its full height behind it, so the selected marker's surroundings stay
visible. From `lg` up it is the same resizable rail it always was.

**Four tables scroll inside their own box.** `TrustBreakdown`, `FactorBreakdown`,
both `RbacMatrix` tables and the six-column adjudication neighbours table. Note
that `.prov-table th` is `white-space: nowrap` and that applies to row headers
too, so these overflow rather than wrap — an API path or a factor label is
genuinely wider than a phone. The neighbours table also keeps a legible
`min-w-[34rem]` below `lg` rather than compressing six numeric columns into
slivers; `lg:min-w-0` hands the desktop back its `w-full` layout.

**Map overlays are compacted, not collapsed.** Tighter padding and width caps
(40vw / 44vw / 62vw) so the layer toggles and the wind readout can never meet in
the middle of a 390px map. Collapsing them behind disclosures was considered and
rejected: forcing a `<details>` open at desktop widths needs both a `display`
override and a `::details-content { content-visibility: visible }`, which behave
differently across engines, and a failure there would break the *desktop*
rendering this update promised not to touch. A layer you cannot see is a layer
you cannot turn on, so they stay visible and get tighter instead. Revisit if the
corner panels prove too heavy in real use.

## Desktop is unchanged, and that is tested

Every rule added here is either inside the sub-1024px token block or written as a
mobile base with an `lg:`/`xl:` reset back to the previous value. The 1440px
visual baselines were re-run and match; they were not regenerated, which is the
point — a regenerated baseline would have hidden exactly the regression this
guarantee is about.

## Test gate

- `apps/web`: 300 unit tests, 26 files — pass, no changes needed. The single-DOM
  chrome is why: every existing `getByRole` query still matches exactly once.
- `tests/architecture`: 54 pass, including `test_brand.py`'s byte-identity check
  between `design/tokens/tokens.css` and `apps/web/src/styles/tokens.css`.
- `e2e --project=mobile`: 12 pass (8 pre-existing, 4 new).
- `e2e --project=chromium`: full desktop suite including the visual baselines.

New e2e coverage, all at 390px:

| Test | What it pins down |
|---|---|
| primary navigation stays reachable | The menu collapses, opens, exposes *every* destination for the role, and closes on Escape |
| every control is a real touch target | Nav links and the menu button measure ≥44px — asserting the token block reached them, not that a component hardcoded a height |
| station detail overlays the map | The map keeps its height when a station opens, and the sheet's top edge sits inside the map's box |
| the sign-in screen fits | The screen the other specs never loaded, because they all start signed in |

`support.ts` gained `openChromeIfCollapsed`, and `gotoRoute` now waits on the
lockup rather than the nav — the nav is behind a button at phone widths, so the
old wait would have hung every mobile spec.

## Superseded

Nothing. This is additive to
`docs/updates/u19-network-map-review-fixes.md` (map overlay positioning) and
`docs/updates/u3-resizable-panel.md` (the desktop drawer, untouched below `lg`).
