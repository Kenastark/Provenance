import { useCallback, useEffect, useRef, useState } from "react";
import { createMapEngine, overlayPadding, type MapEngine } from "./mapEngine";
import { boundsForStations } from "./mapStyle";

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
 */

export interface Positionable {
  lat: number;
  lon: number;
}

export type ProjectFn = (lon: number, lat: number) => { x: number; y: number } | null;

export interface UseMapEngineResult {
  containerRef: (node: HTMLDivElement | null) => void;
  project: ProjectFn;
  /** False when MapLibre could not start; the caller should say so on screen. */
  basemapAvailable: boolean;
  /** True once the map has settled, or immediately when there is no map to settle. */
  isIdle: boolean;
}


export function useMapEngine(stations: readonly Positionable[]): UseMapEngineResult {
  const engineRef = useRef<MapEngine | null>(null);
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const [basemapAvailable, setBasemapAvailable] = useState(true);
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
        onViewChange: () => {
          setIsIdle(false);
          setViewVersion((version) => version + 1);
        },
        onReady: () => setViewVersion((version) => version + 1),
        onIdle: () => setIsIdle(true),
      });
      setBasemapAvailable(true);
    } catch {
      engineRef.current = null;
      setBasemapAvailable(false);
      // There is no map to settle, so the fallback plot is idle as soon as it has
      // a container to measure.
      setIsIdle(true);
    }
  }, []);

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

  useEffect(() => () => engineRef.current?.destroy(), []);

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

  return { containerRef, project, basemapAvailable, isIdle };
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
