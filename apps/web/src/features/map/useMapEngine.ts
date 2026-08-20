import { useCallback, useEffect, useRef, useState } from "react";
import { createMapEngine, overlayPadding, type MapEngine } from "./mapEngine";
import {
  boundsForStations,
  buildBasemapStyle,
  LOCAL_BASEMAP_URL,
  probeBasemap,
  probeGlyphs,
  resolveStyle,
} from "./mapStyle";

/**
 * Owning the GL map, and surviving without one.
 *
 * Two things here are load-bearing:
 *
 * 1. The engine is attached through a **callback ref**, not a mount effect. The
 *    map container does not exist on the first render - the screen shows a loading
 *    state until the stations arrive - so an effect with an empty dependency list
 *    runs against a null container and never retries. The map then stays blank on
 *    a page that is otherwise working perfectly.
 * 2. If MapLibre cannot start (no WebGL, a locked-down VM, a remote desktop with
 *    no acceleration) the screen degrades to a plain relative-position plot rather
 *    than to nothing. Marker positions then come from a linear scale over the
 *    stations' own bounding box: no basemap, no claim of one, but the network's
 *    shape and every station's trust state still readable.
 *
 * Teardown lives only in the callback ref (destroy-then-null when it is called with
 * a new node or with `null`), never in a separate `useEffect(() => () => ..., [])`.
 * React 18 StrictMode double-invokes an effect's cleanup in development — such an
 * effect would destroy the engine the ref just created, with nothing left to
 * recreate it, and the map would sit on the token ground forever, stuck "moving".
 * The ref callback is not subject to that double-invoke, so it is the only safe
 * place for this cleanup.
 */

export interface Positionable {
  lat: number;
  lon: number;
}

export type ProjectFn = (lon: number, lat: number) => { x: number; y: number } | null;

export interface UseMapEngineResult {
  containerRef: (node: HTMLDivElement | null) => void;
  project: ProjectFn;
  /** False when MapLibre could not start at all - no WebGL, a locked-down VM. The
   *  caller should say so on screen; this is a browser/environment problem. */
  basemapAvailable: boolean;
  /** Whether the fetched street basemap is actually being served. `null` until the
   *  probe resolves (the caller should stay quiet during that window, since the
   *  common case - streets present - resolves almost immediately); `false` once the
   *  probe has run and found no archive. Independent of `basemapAvailable`: MapLibre
   *  can be running perfectly on the token ground. */
  tilesPresent: boolean | null;
  /** True once the map has settled, or immediately when there is no map to settle. */
  isIdle: boolean;
}


export function useMapEngine(
  stations: readonly Positionable[],
  theme: "dark" | "light",
): UseMapEngineResult {
  const engineRef = useRef<MapEngine | null>(null);
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const [basemapAvailable, setBasemapAvailable] = useState(true);
  // Whether the fetched street basemap is actually present. Starts null (not yet
  // probed) and only resolves to true or false once the probe answers, so the
  // default everywhere - fresh clone, CI, every test - is the token ground with no
  // premature claim either way.
  const [basemapPresent, setBasemapPresent] = useState<boolean | null>(null);
  // Same tri-state, for the fetched glyph fonts (ADR 0011): null until probed,
  // then whether street/place labels are actually being served.
  const [glyphsPresent, setGlyphsPresent] = useState<boolean | null>(null);
  const [engineGeneration, setEngineGeneration] = useState(0);
  const [viewVersion, setViewVersion] = useState(0);
  const [isIdle, setIsIdle] = useState(false);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const containerRef = useCallback((node: HTMLDivElement | null) => {
    if (nodeRef.current === node) return;

    engineRef.current?.destroy();
    engineRef.current = null;
    nodeRef.current = node;
    if (!node) return;

    setSize({ width: node.clientWidth, height: node.clientHeight });
    try {
      engineRef.current = createMapEngine({
        container: node,
        // Always start on the token ground; the style effect below swaps in the
        // basemap once the probe confirms it, and re-themes on a theme change.
        initialStyle: resolveStyle(),
        onViewChange: () => {
          setIsIdle(false);
          setViewVersion((version) => version + 1);
        },
        onReady: () => setViewVersion((version) => version + 1),
        onIdle: () => setIsIdle(true),
      });
      setBasemapAvailable(true);
      // Signal that an engine exists, so the style effect runs against it.
      setEngineGeneration((generation) => generation + 1);
    } catch {
      engineRef.current = null;
      setBasemapAvailable(false);
      // There is no map to settle, so the fallback plot is idle as soon as it has
      // a container to measure.
      setIsIdle(true);
    }
  }, []);

  // Probe once for the fetched basemap. Absence is the normal case and resolves to
  // false, leaving the token ground in place.
  useEffect(() => {
    const controller = new AbortController();
    probeBasemap(LOCAL_BASEMAP_URL, controller.signal).then(setBasemapPresent).catch(() => {});
    return () => controller.abort();
  }, []);

  // Probe once for the fetched glyph fonts (ADR 0011). Absence is the normal case
  // and resolves to false, leaving street/place labels stripped from the style.
  useEffect(() => {
    const controller = new AbortController();
    probeGlyphs(undefined, controller.signal).then(setGlyphsPresent).catch(() => {});
    return () => controller.abort();
  }, []);

  // Re-apply the style when the theme or basemap presence *changes* - which
  // re-themes the token ground (`resolveStyle` reads the `--prov-map-*` tokens at
  // call time) and swaps in the streets once the probe confirms them.
  //
  // The engine is created with the correct initial style already, so the first run
  // here is a no-op: calling setStyle again mid-load restarts the render cycle and
  // the map never reaches `idle`. A ref, not the engine generation, gates it, so a
  // remount re-arms the skip.
  const styleApplied = useRef<{ theme: string; showBasemap: boolean; showGlyphs: boolean } | null>(
    null,
  );
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;
    void engineGeneration; // re-run after a fresh engine mounts
    // Not-yet-probed and confirmed-absent both mean "stay on the token ground", so
    // they bucket together here; only the UI notice needs the raw tri-state. Labels
    // only ever matter once the basemap itself is showing - the token ground has no
    // symbol layers to label - so glyph presence is irrelevant on its own.
    const showBasemap = basemapPresent === true;
    const showGlyphs = showBasemap && glyphsPresent === true;
    const last = styleApplied.current;
    styleApplied.current = { theme, showBasemap, showGlyphs };
    // Skip the redundant apply on the first run against a given engine; only act on
    // an actual change of theme, basemap presence, or glyph presence.
    if (
      last === null ||
      (last.theme === theme && last.showBasemap === showBasemap && last.showGlyphs === showGlyphs)
    )
      return;
    engine.applyStyle(showBasemap ? buildBasemapStyle(theme, undefined, showGlyphs) : resolveStyle());
  }, [engineGeneration, theme, basemapPresent, glyphsPresent]);

  // Keep the fallback projection honest about the container it is drawing into.
  useEffect(() => {
    const node = nodeRef.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      setSize({ width: node.clientWidth, height: node.clientHeight });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [basemapAvailable]);

  useEffect(() => {
    if (stations.length > 0) engineRef.current?.fitStations(stations);
  }, [stations]);

  const project = useCallback<ProjectFn>(
    (lon, lat) => {
      // Referenced so the projection recomputes as the viewport moves.
      void viewVersion;
      const engine = engineRef.current;
      if (engine) return engine.project(lon, lat);
      const node = nodeRef.current;
      return fallbackProject(
        lon,
        lat,
        stations,
        size,
        node ? overlayPadding(node) : undefined,
      );
    },
    [viewVersion, stations, size],
  );

  return { containerRef, project, basemapAvailable, tilesPresent: basemapPresent, isIdle };
}

/** A linear scale over the station bounding box. Not cartography — a scatter plot. */
export function fallbackProject(
  lon: number,
  lat: number,
  stations: readonly Positionable[],
  size: { width: number; height: number },
  padding: { top: number; bottom: number; left: number; right: number } = {
    top: 96,
    bottom: 96,
    left: 96,
    right: 96,
  },
): { x: number; y: number } | null {
  const bounds = boundsForStations(stations);
  if (!bounds || size.width === 0 || size.height === 0) return null;

  const [[minLon, minLat], [maxLon, maxLat]] = bounds;
  const spanLon = maxLon - minLon || 1;
  const spanLat = maxLat - minLat || 1;
  const innerWidth = Math.max(1, size.width - padding.left - padding.right);
  const innerHeight = Math.max(1, size.height - padding.top - padding.bottom);

  return {
    x: padding.left + ((lon - minLon) / spanLon) * innerWidth,
    // Latitude increases northwards; screen y increases downwards.
    y: padding.top + ((maxLat - lat) / spanLat) * innerHeight,
  };
}
