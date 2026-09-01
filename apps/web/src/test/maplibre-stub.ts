/**
 * A stand-in for maplibre-gl under jsdom.
 *
 * The real module touches `URL.createObjectURL` and a WebGL context at import time,
 * neither of which exists in jsdom - importing it fails before a single assertion
 * runs. Vitest aliases the package to this file (see vite.config.ts) so component
 * tests can render the map screen and check the parts that matter: the markers, the
 * legend, the layer toggles, the wind readout, and the detail panel. Those are all
 * React DOM by design, precisely so they remain testable and accessible.
 *
 * The GL map itself is covered by the Playwright e2e, which runs a real browser.
 */

class StubMap {
  constructor(public options: unknown) {}
  addControl() {
    return this;
  }
  on() {
    return this;
  }
  project(coordinates: [number, number]) {
    // A deterministic, monotonic pseudo-projection. It never claims to be correct
    // cartography; it exists so a marker gets a stable, distinct position and a
    // snapshot does not move between runs.
    const [lon, lat] = coordinates;
    return { x: (lon - 21) * 1000, y: (48 - lat) * 1000 };
  }
  fitBounds() {
    return this;
  }
  setStyle() {
    return this;
  }
  resize() {
    return this;
  }
  remove() {
    return this;
  }
}

class StubControl {}

export const Map = StubMap;
export const NavigationControl = StubControl;
export const ScaleControl = StubControl;

export default {
  Map: StubMap,
  NavigationControl: StubControl,
  ScaleControl: StubControl,
};
