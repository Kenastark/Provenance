# Design

## Assets

| Path | What it is |
|---|---|
| `logo/provenance-mark.svg` | Primary mark. Ring of six nodes, spokes, verified centre node. |
| `logo/provenance-mark-16.svg` | Small-size reduction. Below ~24px the ring and spokes collapse into noise; this keeps the element that carries the meaning. |
| `logo/provenance-mark-mono.svg` | One ink. Uses `currentColor`, so set `color` on the parent. |
| `logo/provenance-lockup-horizontal.svg` | Mark + wordmark. Primary chrome usage. |
| `logo/provenance-lockup-stacked.svg` | Mark + wordmark + descriptor. Marketing, login, title card. |
| `logo/provenance-appicon.svg` | Mobile app icon, 512px, navy plate. |
| `logo/provenance-logo-source.png` | The approved artwork the vectors were rebuilt from. |
| `tokens/tokens.css` | The single source of truth for colour, type, spacing, and state. |

## The palette did not change

`tokens/tokens.css` carries the agreed palette: **Trust Blue**, **Sentinel
Green**, **Alert Amber**, Signal Red, and cool neutrals. The logo did not
override it and should not.

The mark's own three values live separately as `--prov-brand-ink`,
`--prov-brand-blue`, and `--prov-brand-teal`. They are marginally cooler and more
saturated than the UI equivalents, which is normal — a brand mark usually sits a
little hotter than the chrome around it. **They are for the mark only.**

If you would rather the mark sat exactly on the UI palette, it is one command,
and the geometry is unchanged either way:

    cd design/logo
    sed -i '' -e 's/#031436/#071A33/g; s/#0B52C4/#1B6AB8/g; s/#06B49A/#16C97E/g' *.svg
    cp provenance-mark.svg ../../apps/web/public/provenance-mark.svg

Look at it against the dark dashboard shell before deciding. On `--prov-slate-900`
the hotter version reads more clearly at 28px in the top bar, which is the
argument for leaving it alone.

## Two things to know

**The SVG wordmark still depends on a webfont.** Before any of these is used as a
final asset — a submission deck, a printed poster — the text must be converted to
outlines. The mark itself is pure geometry and is safe as-is.

**`tokens/tokens.css` is mirrored into `apps/web/src/styles/tokens.css`.** Edit
the file in `design/` and copy it across; never edit the copy. A CI check fails if
they drift. No colour or type value belongs anywhere in the application except as
a token reference.

## The rules the tokens encode

1. **Blue is the only interactive colour.** Green, amber and red mean *state*. A
   green button would break the code an operator is learning to read on the map.
2. **Green means verified** — which is exactly what the logo's centre node is
   doing. The mark is the product's healthy state, so brand and status are one
   system rather than two competing ones.
3. **The gradient is for the logo only.** Never a UI surface, never a background.
4. **Colour is never the only channel.** Every state has a matching shape token,
   because roughly one man in twelve has a colour-vision deficiency and this
   interface can feed a public-health decision.

Full rationale, component specs, and the screens to mock: see
`provenance-design-brief-v1.1-logo-integration.md`.
