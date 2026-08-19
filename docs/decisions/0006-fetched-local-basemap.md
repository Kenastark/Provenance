# 6. A fetched local street basemap, offline after first setup

Date: 2026-08-09
Status: accepted
Phase: 3 (flag review)
Amends: [0005](0005-basemap-and-map-overlay.md)

## Context

ADR 0005 decided the map ships **no tile data**: out of the box a token-coloured
ground with a graticule, real station positions, `VITE_MAP_STYLE_URL` as the escape
hatch to any MapLibre style. The phase-3 flag review escalated a question that ADR
left open: for the 4 September demo, should the map show real streets, so an
operator sees a station's relationship to a junction they recognise rather than a
dot on grey?

Three options were on the table:

- **A. Keep the token ground.** Offline-guaranteed, no licence exposure, but no
  street context.
- **B. A hosted tile source.** The most persuasive map, one env var — but it puts
  conference wifi on the critical path, which `docs/demo/README.md` forbids ("The
  demo runs offline. Conference wifi fails; assume it.").
- **C. A local extract, fetched at setup.** Real streets, offline after the first
  fetch, at the cost of a fetch step and a decision about where the tile file lives.

The project lead chose **C**, fetched at setup, not committed to the repo, and
accepted that the first setup needs network access.

## Decision

`make basemap` (`scripts/fetch-basemap.sh`) downloads the `go-pmtiles` CLI for the
platform into a gitignored cache, finds a recent Protomaps daily planet build, and
extracts **only the Debrecen bounding box** — about 6 MB — into a gitignored path
under `apps/web/public/basemap/`. The dashboard renders it under the markers when
it is present, and falls back to the token ground when it is not.

`make demo` runs `make basemap`, but never fails on it: no network, no streets, the
demo still runs.

Rendering uses the maintained `@protomaps/basemaps` layer definitions over a local
`pmtiles://` source, with the **symbol (label) layers filtered out** so the map
needs no glyph fonts and is fully offline: streets, water, land use, buildings — no
labels. The GRAYSCALE / DARK flavours are used because they are neutral; a saturated
basemap would compete with the marker palette, where Sentinel Green means *verified*
and Trust Blue is the only interactive colour. OSM is credited on the source.

## Consequences

Good:

- The demo map shows real geography and stays fully offline after the first fetch —
  the point of the escalation, without breaking the offline constraint of B.
- The tiles are never committed: no large binary in git history (rule 10), and a
  fresh clone and every CI run simply have no tiles and use the token ground. So the
  streets are a local enhancement that nothing in the test suite depends on.
- The token-ground default, the DOM markers, and MapLibre-over-Mapbox from ADR 0005
  are all unchanged. This ADR refines 0005; it does not reverse it.

Bad, and accepted:

- The first `make basemap` needs network access. The project lead accepted this.
- The basemap is not under visual regression — its tiles come from an upstream
  planet that changes daily, so a pixel baseline would be meaningless. The visual
  gate deliberately drops the basemap and tests the token ground (the CI/fresh-clone
  state). The basemap's own code — the style builder, the presence probe — is unit
  tested instead.
- The extract is pinned to a CLI version and a public planet host. If either moves,
  `make basemap` fails loudly and the demo falls back to the token ground; the map
  still works, it just loses the streets until the script is updated.

## Notes

Two things were found the hard way and are worth recording:

- **Presence must be detected by content, not a status code.** The dashboard is a
  single-page app; its dev and preview servers answer *any* unknown path with
  `index.html` and a 200. A HEAD probe therefore reports the basemap "present" when
  the file is absent, and the pmtiles loader then chokes on HTML ("Wrong magic
  number") and leaves the map stuck loading. The probe reads the first seven bytes
  and checks the `PMTiles` archive magic. A regression test covers the SPA-fallback
  case.
- **Re-styling the map on load hangs it.** Calling `setStyle` again while the first
  style is still loading restarts the render cycle and the map never reaches `idle`.
  The engine is created with the correct initial style, and the style is only
  re-applied on an actual theme or basemap-presence *change* — which, as a side
  effect, fixed a latent bug where the token ground never re-themed on a theme
  switch.
