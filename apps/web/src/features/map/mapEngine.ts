import { Protocol as PMTilesProtocol } from "pmtiles";
import maplibregl, { type Map as MapLibreMap, type StyleSpecification } from "maplibre-gl";
import { boundsForStations, resolveStyle } from "./mapStyle";

/**
 * Register the pmtiles protocol once, so a `pmtiles://` source can be range-read
 * from a single local archive file.
 *
 * Guarded, because the vitest suite aliases maplibre-gl to a stub that has no
 * `addProtocol` — and the map engine's factory runs under jsdom when a component
 * test mounts the map surface. Without the guard, importing this module would throw
 * there before any assertion ran.
 */
let pmtilesRegistered = false;
function ensurePmtilesProtocol(): void {
  if (pmtilesRegistered) return;
  if (typeof maplibregl.addProtocol !== "function") return;
  maplibregl.addProtocol("pmtiles", new PMTilesProtocol().tile);
  pmtilesRegistered = true;
}

/**
 * The MapLibre binding, kept to one file and one shape.
 *
 * Everything above this line is plain React that renders and tests without WebGL.
 * The engine's only jobs are: own the GL map, tell React when the viewport moved,
 * and turn a coordinate into a pixel. Station markers are React DOM positioned from
 * `project()`, not GL symbols - that way a marker is a real focusable `<button>`
 * with an accessible name, which a GL-rendered sprite can never be.
 *
 * This file is excluded from unit coverage on purpose: jsdom has no WebGL context,
 * so nothing here can execute there. The Playwright e2e drives it in a real browser.
 */

export interface Projected {
  x: number;
  y: number;
}

export interface MapEngine {
  project(lon: number, lat: number): Projected;
  fitStations(stations: readonly { lat?: number | null; lon?: number | null }[]): void;
  /** Swap the whole style — used to bring in the fetched basemap and to re-theme. */
  applyStyle(style: string | StyleSpecification): void;
  /**
   * Force the GL canvas's pixel buffer and CSS box to match its container's
   * current size, right now.
   *
   * MapLibre keeps its own internal `ResizeObserver` (`trackResize`, on by
   * default) and would eventually catch a container resize on its own — but
   * "eventually" is a ~50ms-debounced side channel racing React's own layout
   * commit, and it deliberately skips its own first callback (treating it as
   * the initial measurement rather than a real change). The marker overlay
   * (`MapOverlays.tsx`) has zero such lag: it is plain CSS positioned from
   * `project()`, which reads the map's *current* transform. A caller that
   * knows the container just changed size (the resizable drawer's
   * `ResizeObserver` in `useMapEngine.ts`) should call this synchronously with
   * that knowledge, rather than trust MapLibre's own implicit side channel to
   * resolve before the next paint.
   */
  resize(): void;
  destroy(): void;
}

export interface CreateMapEngineOptions {
  container: HTMLElement;
  onViewChange: () => void;
  onReady: () => void;
  /** Fired when the map has finished moving and rendering. */
  onIdle: () => void;
  /** The style to start with. Defaults to the token ground; the hook may swap in
   *  the fetched basemap once it has confirmed the tiles are present. */
  initialStyle?: string | StyleSpecification;
}

export function createMapEngine({
  container,
  onViewChange,
  onReady,
  onIdle,
  initialStyle,
}: CreateMapEngineOptions): MapEngine {
  ensurePmtilesProtocol();
  // The very first fit jumps straight to the final view instead of easing to it.
  // Confirmed live against production (real DEB-KER12 data, real network latency
  // to the GCS-backed pmtiles archive): an eased fitBounds keeps the camera moving
  // for ~300-600ms, and MapLibre cancels each batch of in-flight tile/pmtiles-
  // directory-chunk requests as the camera supersedes them. The archive itself was
  // verified to hold real tile content at every zoom for DEB-KER12's location (the
  // network's easternmost station) via `pmtiles tile` - so a permanently blank
  // patch under its marker is a cancelled request that never got retried once the
  // camera settled, not missing data. Local dev never surfaces this: a same-origin
  // pmtiles file resolves each range request fast enough that the churn never
  // outlasts the animation. A later re-fit (the `stations` list changing after the
  // engine already has a settled view) keeps the eased eye-candy - it is not the
  // cold-load path this only starts moving from a neutral, tile-free world view.
  let hasFitOnce = false;
  const map: MapLibreMap = new maplibregl.Map({
    container,
    style: initialStyle ?? resolveStyle(),
    // No hardcoded centre: the view is fitted to the stations the API returns as
    // soon as they arrive. Until then, a neutral world view.
    center: [0, 0],
    zoom: 1,
    attributionControl: { compact: true },
    // The reduced-motion preference has to reach the map too, not just CSS.
    fadeDuration: prefersReducedMotion() ? 0 : 300,
  });

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

  map.on("move", onViewChange);
  map.on("zoom", onViewChange);
  map.on("load", () => {
    onReady();
    onViewChange();
  });
  // MapLibre's own settled signal: no pending transitions, no tiles in flight,
  // nothing left to draw. The overlay marks itself idle from this, which gives the
  // e2e a real readiness condition to wait on instead of a sleep, and gives the
  // visual snapshots a stable frame.
  map.on("idle", onIdle);
  map.on("movestart", onViewChange);

  return {
    project(lon, lat) {
      const point = map.project([lon, lat]);
      return { x: point.x, y: point.y };
    },
    fitStations(stations) {
      const bounds = boundsForStations(stations);
      if (!bounds) return;
      const immediate = !hasFitOnce;
      hasFitOnce = true;
      map.fitBounds(bounds, {
        padding: overlayPadding(container),
        maxZoom: 13,
        duration: immediate || prefersReducedMotion() ? 0 : 600,
      });
    },
    applyStyle(style) {
      // diff:true keeps the camera and only swaps the changed layers, so bringing
      // in the basemap or re-theming does not throw the view back to the start.
      map.setStyle(style, { diff: true });
    },
    resize() {
      map.resize();
    },
    destroy() {
      map.remove();
    },
  };
}

/**
 * Space reserved for the overlay panels when fitting the network.
 *
 * The panels float over the map - layer toggles top-left, wind top-right, legend
 * bottom-right - and a marker fitted underneath one of them cannot be clicked at
 * all: the panel swallows the pointer event. Rather than guess their sizes, this
 * measures them, so the reservation stays correct when the copy or the font
 * changes.
 *
 * Each side is capped at a third of the container, because on a narrow screen the
 * panels are wider than the space available and an unclamped padding would leave
 * MapLibre with a negative viewport.
 */
export function overlayPadding(container: HTMLElement): {
  top: number;
  bottom: number;
  left: number;
  right: number;
} {
  const GUTTER = 16;
  const FALLBACK = { top: 96, bottom: 96, left: 96, right: 96 };
  const section = container.parentElement;
  const width = container.clientWidth || 0;
  const height = container.clientHeight || 0;
  if (!section || width === 0 || height === 0) return FALLBACK;

  const base = section.getBoundingClientRect();
  const panels = section.querySelectorAll<HTMLElement>("[data-map-overlay]");

  const padding = { ...FALLBACK, top: 0, bottom: 0, left: 0, right: 0 };
  for (const panel of panels) {
    const box = panel.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) continue;
    const left = box.left - base.left;
    const top = box.top - base.top;
    // A panel anchored to a side reserves the distance from that side to its far
    // edge; which side it is anchored to is decided by which half it sits in.
    if (left < width / 2) padding.left = Math.max(padding.left, left + box.width + GUTTER);
    else padding.right = Math.max(padding.right, width - left + GUTTER);
    if (top < height / 2) padding.top = Math.max(padding.top, top + box.height + GUTTER);
    else padding.bottom = Math.max(padding.bottom, height - top + GUTTER);
  }

  const capX = Math.floor(width / 3);
  const capY = Math.floor(height / 3);
  return {
    left: Math.min(Math.max(padding.left, 24), capX),
    right: Math.min(Math.max(padding.right, 24), capX),
    top: Math.min(Math.max(padding.top, 24), capY),
    bottom: Math.min(Math.max(padding.bottom, 24), capY),
  };
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined"
    ? Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
    : false;
}
