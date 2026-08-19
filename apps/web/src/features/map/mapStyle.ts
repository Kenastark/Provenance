/**
 * The basemap style, built from the design tokens at runtime.
 *
 * MapLibre needs concrete colour values, and colour literals are not allowed
 * anywhere in src/ except the token file - so the style reads the computed value of
 * `--prov-map-*` off the document. That keeps tokens.css authoritative and makes
 * the basemap re-theme with everything else when the operator switches to light.
 *
 * On the default basemap: the repository ships no tile data and invents no
 * geography. Out of the box the map is a token-coloured ground with a real
 * latitude/longitude graticule, and the stations - whose coordinates are read from
 * the Green Sentinel export - are positioned on it correctly. Point
 * VITE_MAP_STYLE_URL at any MapLibre style (an OpenMapTiles server, a local
 * PMTiles) and that becomes the basemap instead. MapLibre rather than Mapbox is a
 * deliberate choice: a municipal buyer story is stronger on an open stack.
 */

import { DARK, GRAYSCALE, layers as protomapsLayers } from "@protomaps/basemaps";
import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

export const MAP_STYLE_URL: string | undefined = import.meta.env.VITE_MAP_STYLE_URL;

/**
 * Where the fetched Debrecen basemap lives when it is present.
 *
 * `make basemap` extracts a Debrecen vector tile archive into `public/basemap/`,
 * which the dev and preview servers serve from the site root. The file is
 * gitignored and absent by default — a fresh clone, and every CI run, has no tiles
 * and falls back to the token ground below. So the streets are a local-demo
 * enhancement, never a thing tests or CI depend on.
 */
export const LOCAL_BASEMAP_URL = "/basemap/debrecen.pmtiles";

/** The vector source name the Protomaps layer definitions expect. */
const PROTOMAPS_SOURCE = "protomaps";

/** Read a CSS custom property off the document root. */
export function readToken(name: string, root?: HTMLElement): string {
  const element = root ?? (typeof document !== "undefined" ? document.documentElement : null);
  if (!element || typeof getComputedStyle !== "function") return "";
  return getComputedStyle(element).getPropertyValue(name).trim();
}

/** Whole-degree and half-degree lines, generated from real coordinates. */
export function graticule(step = 0.05): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const round = (value: number) => Number(value.toFixed(4));
  for (let lat = 45; lat <= 50; lat = round(lat + step)) {
    features.push({
      type: "Feature",
      properties: { kind: "parallel", value: lat },
      geometry: { type: "LineString", coordinates: [[18, lat], [24, lat]] },
    });
  }
  for (let lon = 18; lon <= 24; lon = round(lon + step)) {
    features.push({
      type: "Feature",
      properties: { kind: "meridian", value: lon },
      geometry: { type: "LineString", coordinates: [[lon, 45], [lon, 50]] },
    });
  }
  return { type: "FeatureCollection", features };
}

/**
 * The fallback style: ground colour plus a graticule, both from tokens.
 *
 * When a token cannot be resolved the layer paints `transparent` rather than a
 * literal colour. There is no hex in this file and there must not be: the brand
 * guard in src/__tests__/no-inline-hex.test.ts fails the build over one, and a
 * hardcoded map colour is exactly the kind of value that stops matching the palette
 * the moment a token changes. Transparent is also the right answer visually - the
 * map container is already painted `--prov-bg`, so an unresolved token degrades to
 * the page background instead of to some other blue.
 */
export function buildFallbackStyle(root?: HTMLElement): StyleSpecification {
  const ground = readToken("--prov-map-ground", root) || "transparent";
  const line = readToken("--prov-map-road", root) || "transparent";

  return {
    version: 8,
    name: "Provenance (token ground)",
    sources: {
      graticule: { type: "geojson", data: graticule() },
    },
    layers: [
      { id: "ground", type: "background", paint: { "background-color": ground } },
      {
        id: "graticule",
        type: "line",
        source: "graticule",
        paint: { "line-color": line, "line-width": 1 },
      },
    ],
  };
}

export function resolveStyle(root?: HTMLElement): string | StyleSpecification {
  return MAP_STYLE_URL ?? buildFallbackStyle(root);
}

/**
 * The real streets, when the fetched basemap is present.
 *
 * Uses the maintained `@protomaps/basemaps` layer definitions over a local PMTiles
 * source, with the **symbol layers removed** so the map needs no glyph fonts and
 * stays fully offline: streets, water, land use, buildings and boundaries, but no
 * labels. Two deliberate choices matter here:
 *
 * 1. The GRAYSCALE / DARK flavours are neutral — greys and blue-greys, no saturated
 *    green or blue. That is not aesthetics: Sentinel Green means *verified* and
 *    Trust Blue is the only interactive colour, so a green park or a blue road on
 *    the basemap would compete with the state the markers carry. The basemap must
 *    sit under the map without arguing with it (tokens.css says exactly this).
 * 2. The flavour tracks the app theme, so the streets re-theme with everything else.
 *
 * The OSM attribution is carried on the source, so MapLibre's own attribution
 * control renders it — the open-stack, correctly-credited story the municipal pitch
 * rests on.
 */
export function buildBasemapStyle(
  theme: "dark" | "light",
  pmtilesUrl: string = LOCAL_BASEMAP_URL,
): StyleSpecification {
  const flavour = theme === "dark" ? DARK : GRAYSCALE;
  const geometryOnly = (protomapsLayers(PROTOMAPS_SOURCE, flavour, { lang: "en" }) as LayerSpecification[]).filter(
    (layer) => layer.type !== "symbol",
  );

  return {
    version: 8,
    // A same-origin absolute URL: the pmtiles protocol needs the archive's full
    // location, not a bare path, to issue range requests against it.
    sources: {
      [PROTOMAPS_SOURCE]: {
        type: "vector",
        url: `pmtiles://${absoluteUrl(pmtilesUrl)}`,
        attribution:
          '<a href="https://openstreetmap.org/copyright" target="_blank" rel="noreferrer">&copy; OpenStreetMap</a>',
      },
    },
    layers: geometryOnly,
  };
}

function absoluteUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  if (typeof window !== "undefined" && window.location) {
    return `${window.location.origin}${path}`;
  }
  return path;
}

/** The ASCII magic every PMTiles v3 archive begins with. */
const PMTILES_MAGIC = "PMTiles";

/**
 * Is a *real* PMTiles archive actually served here?
 *
 * It reads the first seven bytes and checks the archive magic — a HEAD, or trusting
 * a 200, is not enough: the dashboard is a single-page app, and its dev and preview
 * servers answer any unknown path with `index.html` and a 200. A HEAD probe would
 * then report the basemap "present" when the file is absent, and the pmtiles loader
 * would choke on HTML with "Wrong magic number" and leave the map stuck loading. A
 * content check distinguishes the archive from the SPA fallback.
 *
 * Every failure — a 404, an SPA HTML fallback, no `fetch`, a network error —
 * resolves to `false`, and the map keeps the token ground it was created with. That
 * is what lets the streets be a local enhancement that never breaks a fresh clone.
 */
export async function probeBasemap(
  url: string = LOCAL_BASEMAP_URL,
  signal?: AbortSignal,
): Promise<boolean> {
  if (typeof fetch !== "function") return false;
  try {
    const response = await fetch(url, { headers: { Range: `bytes=0-6` }, signal });
    if (!response.ok) return false;
    const magic = new TextDecoder().decode(new Uint8Array(await response.arrayBuffer()).subarray(0, 7));
    return magic === PMTILES_MAGIC;
  } catch {
    return false;
  }
}

/** A bounding box around the stations that have coordinates, with a little margin. */
export function boundsForStations(
  stations: readonly { lat?: number | null; lon?: number | null }[],
): [[number, number], [number, number]] | null {
  const located = stations.filter(
    (s): s is { lat: number; lon: number } =>
      typeof s.lat === "number" && typeof s.lon === "number",
  );
  if (located.length === 0) return null;

  const lats = located.map((s) => s.lat);
  const lons = located.map((s) => s.lon);
  // A single station has zero extent; give it a small box so fitBounds does not
  // zoom to the maximum level.
  const pad = located.length === 1 ? 0.01 : 0;
  return [
    [Math.min(...lons) - pad, Math.min(...lats) - pad],
    [Math.max(...lons) + pad, Math.max(...lats) + pad],
  ];
}
