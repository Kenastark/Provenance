# 11. Local glyph fonts for street labels on the basemap

Date: 2026-08-20
Status: accepted
Phase: post-1.0 (update)
Amends: [0006](0006-fetched-local-basemap.md)

## Context

ADR 0006 chose to strip every symbol (label) layer from the fetched Protomaps
basemap style specifically so the map needed no font-glyph assets and could
stay fully offline after the one-time PMTiles fetch. That traded away street
and place-name labels entirely: real streets, no street names.

A separate bug fix (widening the fetched archive's bounding box so `DEB-KER12`
stopped rendering on blank tiles) raised the same question again while working
in this area: is there a way to get labels back without reintroducing the
live-network dependency ADR 0006 rejected for the demo?

## Decision

Yes — glyph fonts, like the tile archive itself, can be fetched once and
served locally. `scripts/fetch-fonts.sh` mirrors `fetch-basemap.sh`'s contract
exactly (idempotent, loud-but-non-fatal, gitignored output) and downloads the
PBF glyph ranges for the three font weights the Protomaps style actually
references — `"Noto Sans Regular"`, `"Noto Sans Medium"`, `"Noto Sans
Italic"` — covering Unicode ranges `0-255` and `256-511` (Basic Latin +
Latin-1 Supplement + Latin Extended-A). That pair of ranges is what Hungarian
needs: most diacritics (á, é, í, ó, ö, ú, ü) live in Latin-1 Supplement, but
ő and ű live in Latin Extended-A, one range up. Source:
`https://protomaps.github.io/basemaps-assets/fonts/...`, published by
`protomaps` — the same publisher as the `@protomaps/basemaps` npm package
already used for the style itself.

`mapStyle.ts`'s `buildBasemapStyle` gains a `glyphsAvailable` flag: `false`
(the existing default) strips symbol layers exactly as before; `true` keeps
them and adds a `glyphs` URL pointing at the local files. `useMapEngine`
probes for the fonts the same way it already probes for the tile archive — by
content, not status code, since the dev/preview server answers any missing
path with `index.html` and a 200 (the same SPA-fallback trap ADR 0006's own
notes describe for the basemap). A glyph PBF's first byte is reliably `0x0a`
(the protobuf tag for the message's first field, verified against a real
fetched file); an SPA fallback's first byte is `<`. Absence resolves to no
labels, exactly like absence of the basemap resolves to the token ground —
graceful, silent, never a broken map.

## Consequences

Good:

- Real street and place names, sourced from the same OSM data the streets
  themselves already come from, fully offline after the one-time fetch — the
  map reads like a normal map to an operator who knows the city, not a
  geometry diagram.
- Six small files (~450 KB total for the two ranges × three weights actually
  used), fetched from a maintained, versioned OSS asset host operated by the
  same publisher as the style package already depended on.
- Font glyphs are pre-rendered signed-distance-field bitmaps baked into the
  PBF and drawn by MapLibre's own WebGL renderer, not the host OS's font
  rasteriser — unlike the DOM-rendered station-id labels (which is exactly why
  the visual gate is pinned to a single container, per the Makefile's own
  comments on font rasterisation differing between macOS and Linux). Map-canvas
  text should render pixel-identically across platforms. Not yet proven at CI
  scale — see Bad, below.
- No change to the CI/fresh-clone default: `apps/web/public/fonts/` is
  gitignored and absent until `make fonts` (or `make basemap`/`make
  demo`/`make demo-real`, which now call it) runs, so `buildBasemapStyle`'s
  default (`glyphsAvailable = false`) and the entire pre-existing test suite
  are unchanged. The visual-regression gate, already scoped to the
  token-ground state (ADR 0006), is unaffected either way.

Bad, and accepted:

- A second gitignored, network-fetched asset directory to explain to a new
  contributor, alongside the tile archive.
- Only Basic Latin, Latin-1 Supplement and Latin Extended-A are fetched. A
  street or place name using a character outside those three blocks (in
  practice: anything outside a Western/Central European Latin alphabet) will
  render without that glyph. Fine for Debrecen; would need widening — more
  ranges, more font weights — for a different city.
- The cross-platform SDF-rendering claim above is reasoned from how
  MapLibre's glyph pipeline works, not measured against a captured Linux
  baseline: nothing in the current visual gate exercises the labelled state,
  since that gate deliberately tests the token ground.
- `make basemap` and `make fonts` are two independent, non-fatal fetches; a
  partial failure (tiles present, fonts absent, or the reverse) is a real,
  silently-accepted state — the map just shows whichever half succeeded, with
  no notice distinguishing "no streets" from "streets, no labels".

## Notes

Font weight names are fixed by the Protomaps style itself, not chosen here:
symbol layers request exactly `"Noto Sans Regular"`, `"Noto Sans Medium"`,
`"Noto Sans Italic"`, or — for non-Latin scripts, never hit by this network's
real data — `"Noto Sans Devanagari Regular v1"`. The last is deliberately not
fetched.
