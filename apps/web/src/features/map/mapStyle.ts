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

import type { StyleSpecification } from "maplibre-gl";

export const MAP_STYLE_URL: string | undefined = import.meta.env.VITE_MAP_STYLE_URL;

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
