# 5. MapLibre with a token-coloured default basemap, and DOM marker overlays

Date: 2026-08-08
Status: accepted
Phase: 3

## Context

The network map is the dashboard's primary screen. Building it forced three
decisions that are expensive to reverse once other screens depend on them.

**Which map engine.** Already settled in the blueprint and CLAUDE.md: MapLibre GL,
not Mapbox. A municipal buyer story is stronger on an open stack, and Mapbox's
licence terms would put a commercial dependency in the middle of a public-sector
data-integrity product.

**What the basemap shows.** The repository ships no tile data and has no tile
budget. The obvious options were: (a) point at a public tile server, which makes the
demo dependent on someone else's uptime and puts a network call in CI; (b) draw
Debrecen's streets and water ourselves, which means inventing geography; (c) ship no
basemap.

**How markers are drawn.** MapLibre can render markers as GL symbols, which is fast
and correct cartographically, or as DOM elements positioned from the map's
projection.

## Decision

**Basemap.** The default is a token-coloured ground plus a real latitude/longitude
graticule, and nothing else. `VITE_MAP_STYLE_URL` points the map at any MapLibre
style — an OpenMapTiles server, a local PMTiles archive — and that becomes the
basemap instead.

Station positions are real either way: coordinates are parsed from the Green
Sentinel export's `Location` column, and the fixture corpus carries an explicit
`stations.json` sidecar rather than having coordinates guessed for it.

**Markers.** React DOM, absolutely positioned from `map.project()`, not GL symbols.

**Degradation.** If MapLibre cannot start at all — no WebGL, a locked-down VM, a
remote desktop without acceleration — the screen falls back to a linear scale over
the stations' own bounding box and says so on screen. No basemap, no claim of one,
but the network's shape and every station's trust state stay readable.

## Consequences

Good:

- Nothing in the repository invents geography. Rule 2 says never invent field names,
  units, or station identifiers; drawing a plausible-looking street network would be
  the same failure in a different medium.
- The demo and CI are offline and deterministic. No tile server can be down at 09:00
  on the day of the pitch.
- Every marker is a real `<button>` with an accessible name and a tab stop. A GL
  sprite cannot be either, and this is an operations screen that has to be
  keyboard-navigable end to end.
- Component tests render the whole overlay under jsdom, because none of it needs
  WebGL. The GL binding is one file, excluded from unit coverage and covered by the
  Playwright suite in a real browser.

Bad, and accepted:

- Out of the box the map has no streets, so a station's position is legible relative
  to the other stations rather than relative to a junction an operator knows. For the
  municipality's own deployment this is a one-line configuration change, and for the
  demo the network's *shape* is what carries the argument.
- DOM markers do not scale to thousands of points. At 18 stations, and with the
  wind-conditioned graph of phase 4 adding edges between the same 18, that ceiling is
  far away. If a later phase plots every traffic counter, the marker layer will need
  revisiting — it is deliberately a single component behind a `project()` function so
  that swap is contained.

## Notes

Two implementation details are load-bearing enough to record, because both were
discovered by a test failing rather than by review:

- The overlay panels float in the map's corners, and a marker fitted underneath one
  cannot be clicked at all — the panel swallows the pointer event. `fitBounds`
  measures the panels (`[data-map-overlay]`) and reserves their footprint.
- `overflow: hidden` on a *statically* positioned element does not clip
  absolutely-positioned descendants. The app shell therefore sets `position:
  relative` alongside it, without which the marker overlay escaped the shell and the
  whole page scrolled sideways at 390px.
