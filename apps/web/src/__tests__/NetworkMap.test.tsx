import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NetworkMap } from "../features/map/NetworkMap";
import {
  buildBusStopMarkers,
  buildStationMarkers,
  buildTrafficCounterMarkers,
  compassPoint,
  currentWind,
  MAP_LAYERS,
  resolveMapLayers,
  summariseMarkers,
  visibleStationLabels,
} from "../features/map/stationMarkers";
import {
  boundsForStations,
  buildBasemapStyle,
  buildFallbackStyle,
  graticule,
  LOCAL_BASEMAP_URL,
  probeBasemap,
  probeGlyphs,
} from "../features/map/mapStyle";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

describe("marker model", () => {
  it("joins stations, quality and events into one marker per located station", () => {
    const { markers, withoutCoordinates } = buildStationMarkers({
      stations: fixtures.stations,
      quality: fixtures.qualitySummary.stations,
      events: fixtures.events,
    });

    expect(markers.map((m) => m.stationId)).toEqual(["STA-01", "STA-02", "STA-03"]);
    // A station with no coordinates is reported, never dropped.
    expect(withoutCoordinates).toEqual(["STA-04"]);
  });

  it("colours a marker by its trust state and marks an active event separately", () => {
    const { markers } = buildStationMarkers({
      stations: fixtures.stations,
      quality: fixtures.qualitySummary.stations,
      events: fixtures.events,
    });
    const byId = Object.fromEntries(markers.map((m) => [m.stationId, m]));

    expect(byId["STA-02"]?.state).toBe("verified");
    expect(byId["STA-01"]?.state).toBe("degraded");
    expect(byId["STA-03"]?.state).toBe("fault");
    // STA-03 carries the ranked event; STA-02 does not.
    expect(byId["STA-03"]?.hasActiveEvent).toBe(true);
    expect(byId["STA-02"]?.hasActiveEvent).toBe(false);
  });

  it("keeps the highest-ranked event when a station has several", () => {
    const { markers } = buildStationMarkers({
      stations: [fixtures.station()],
      quality: [],
      events: [
        fixtures.provEvent({ id: 1, rank: 4, station_id: "STA-01", headline: "lower rank" }),
        fixtures.provEvent({ id: 2, rank: 1, station_id: "STA-01", headline: "top rank" }),
      ],
    });
    expect(markers[0]?.eventHeadline).toBe("top rank");
  });

  it("treats an unscored station as unknown rather than as a fault", () => {
    const { markers } = buildStationMarkers({
      stations: [fixtures.station({ station_id: "STA-04" })],
      quality: [fixtures.qualityStation({ station_id: "STA-04", trust: null })],
      events: [],
    });
    expect(markers[0]?.state).toBe("unknown");
  });

  it("summarises the network by state", () => {
    const { markers } = buildStationMarkers({
      stations: fixtures.stations,
      quality: fixtures.qualitySummary.stations,
      events: [],
    });
    expect(summariseMarkers(markers)).toEqual({
      verified: 1,
      degraded: 1,
      fault: 1,
      unknown: 0,
    });
  });
});

describe("reference layers", () => {
  it("builds bus-stop markers from real GTFS coordinates, all measured", () => {
    const markers = buildBusStopMarkers(fixtures.referenceStopsAvailable.stops);
    expect(markers.map((m) => m.stopId)).toEqual(["S-STA-01-0", "S-STA-02-0"]);
    expect(markers.every((m) => m.provenance === "measured")).toBe(true);
  });

  it("builds traffic-counter markers from real Enclod coordinates, all measured", () => {
    const markers = buildTrafficCounterMarkers(fixtures.referenceCountersAvailable.counters);
    expect(markers).toHaveLength(2);
    expect(markers.every((m) => m.provenance === "measured")).toBe(true);
  });

  it("keeps a layer disabled while its query is still loading", () => {
    const layers = resolveMapLayers(MAP_LAYERS, { busStops: undefined, trafficCounters: undefined });
    const busStop = layers.find((l) => l.id === "busStop")!;
    expect(busStop.available).toBe(false);
    expect(busStop.unavailableReason).toBeTruthy();
  });

  it("enables a layer once its reference endpoint reports real data", () => {
    const layers = resolveMapLayers(MAP_LAYERS, {
      busStops: fixtures.referenceStopsAvailable,
      trafficCounters: fixtures.referenceCountersUnavailable,
    });
    const busStop = layers.find((l) => l.id === "busStop")!;
    const trafficCounter = layers.find((l) => l.id === "trafficCounter")!;
    expect(busStop.available).toBe(true);
    expect(busStop.unavailableReason).toBeUndefined();
    expect(trafficCounter.available).toBe(false);
    expect(trafficCounter.unavailableReason).toMatch(/provisional placeholders/);
  });
});

describe("wind", () => {
  it("averages bearings as vectors so the 360/0 wrap does not point backwards", () => {
    // A naive mean of 350 and 10 is 180 - the exact opposite direction.
    const wind = currentWind(fixtures.windReadings);
    expect(wind).not.toBeNull();
    expect(wind!.directionDegrees).toBeCloseTo(0, 5);
    expect(wind!.speed).toBeCloseTo(12.5);
    expect(wind!.stationCount).toBe(2);
  });

  it("returns null when no wind was measured, rather than reporting a calm", () => {
    expect(currentWind([])).toBeNull();
    expect(currentWind(fixtures.readings)).toBeNull();
  });

  it("names a bearing on the compass", () => {
    expect(compassPoint(0)).toBe("N");
    expect(compassPoint(90)).toBe("E");
    expect(compassPoint(180)).toBe("S");
    expect(compassPoint(270)).toBe("W");
    expect(compassPoint(361)).toBe("N");
  });
});

describe("basemap style", () => {
  it("bounds the view to the stations that have coordinates", () => {
    expect(boundsForStations(fixtures.stations)).toEqual([
      [21.502204, 47.559175],
      [21.520204, 47.577175],
    ]);
  });

  it("returns no bounds when nothing can be placed", () => {
    expect(boundsForStations([])).toBeNull();
    expect(boundsForStations([{ lat: null, lon: null }])).toBeNull();
  });

  it("gives a single station a box rather than zooming to maximum", () => {
    const bounds = boundsForStations([{ lat: 47.5, lon: 21.5 }]);
    expect(bounds![0][0]).toBeLessThan(bounds![1][0]);
    expect(bounds![0][1]).toBeLessThan(bounds![1][1]);
  });

  it("builds a style with no hardcoded colour when tokens are unresolved", () => {
    const style = buildFallbackStyle();
    expect(style.layers[0]).toMatchObject({ id: "ground", type: "background" });
    // jsdom resolves no custom properties, so the fallback must be a keyword.
    expect(JSON.stringify(style)).not.toMatch(/#[0-9a-fA-F]{3,8}/);
  });

  it("generates the graticule from real coordinates", () => {
    const lines = graticule(1);
    expect(lines.features.length).toBeGreaterThan(0);
    for (const feature of lines.features) {
      expect(feature.geometry.type).toBe("LineString");
    }
  });
});

describe("NetworkMap", () => {
  it("renders one marker per located station", async () => {
    renderWithProviders(<NetworkMap />);
    await waitFor(() => expect(screen.getAllByTestId("station-marker")).toHaveLength(3));
  });

  it("names every marker for assistive technology", async () => {
    renderWithProviders(<NetworkMap />);
    const markers = await screen.findAllByTestId("station-marker");
    for (const marker of markers) {
      expect(marker.getAttribute("aria-label")).toMatch(/STA-\d+/);
    }
  });

  it("reports stations that could not be mapped", async () => {
    renderWithProviders(<NetworkMap />);
    expect(await screen.findByTestId("stations-without-coordinates")).toHaveTextContent("STA-04");
  });

  it("opens the station detail when a marker is activated", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NetworkMap />);

    const markers = await screen.findAllByTestId("station-marker");
    await user.click(markers[0]!);

    const panel = await screen.findByTestId("station-detail-panel");
    expect(within(panel).getByRole("heading", { level: 2 })).toHaveTextContent("STA-01");
  });

  it("carries a legend counting each state", async () => {
    renderWithProviders(<NetworkMap />);
    const legend = await screen.findByTestId("map-legend");
    expect(within(legend).getByText("Verified")).toBeInTheDocument();
    expect(within(legend).getByText("Fault")).toBeInTheDocument();
  });

  it("keeps BusStop and TrafficCounter disabled with an honest reason when no drop is loaded", async () => {
    renderWithProviders(<NetworkMap />);

    const busStopToggle = await screen.findByTestId("layer-toggle-busStop");
    expect(busStopToggle).toBeDisabled();
    expect(busStopToggle.closest("label")).toHaveAttribute("title", expect.stringMatching(/GTFS bundle not loaded/));

    const trafficToggle = await screen.findByTestId("layer-toggle-trafficCounter");
    expect(trafficToggle).toBeDisabled();
    expect(trafficToggle.closest("label")).toHaveAttribute(
      "title",
      expect.stringMatching(/provisional placeholders/),
    );
  });

  it("enables BusStop once the GTFS bundle is loaded and draws subordinate, measured markers", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NetworkMap />, {
      routes: { "/v1/reference/bus-stops": fixtures.referenceStopsAvailable },
    });

    const toggle = await screen.findByTestId("layer-toggle-busStop");
    expect(toggle).toBeEnabled();
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    expect(toggle).toBeChecked();

    const layer = await screen.findByTestId("reference-marker-layer-bus-stop");
    const markers = within(layer).getAllByTestId("reference-marker");
    expect(markers).toHaveLength(fixtures.referenceStopsAvailable.stops.length);
    for (const marker of markers) {
      expect(marker).toHaveAttribute("data-kind", "bus-stop");
      expect(marker).toHaveAttribute("data-provenance", "measured");
    }
  });

  it("enables TrafficCounter once real Enclod coordinates are loaded", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NetworkMap />, {
      routes: { "/v1/reference/traffic-counters": fixtures.referenceCountersAvailable },
    });

    const toggle = await screen.findByTestId("layer-toggle-trafficCounter");
    expect(toggle).toBeEnabled();
    await user.click(toggle);

    const layer = await screen.findByTestId("reference-marker-layer-traffic-counter");
    const markers = within(layer).getAllByTestId("reference-marker");
    expect(markers).toHaveLength(fixtures.referenceCountersAvailable.counters.length);
    for (const marker of markers) {
      expect(marker).toHaveAttribute("data-kind", "traffic-counter");
      expect(marker).toHaveAttribute("data-provenance", "measured");
    }
  });

  it("distinguishes marker provenance in the legend", async () => {
    renderWithProviders(<NetworkMap />);
    const legend = await screen.findByTestId("map-legend");
    // Stations are always measured, so the legend always carries this row -
    // and never a "provisional" one, since the map refuses to draw those.
    expect(within(legend).getByTestId("map-legend-provenance")).toHaveTextContent(/Measured position/);
    expect(within(legend).queryByText(/Provisional/)).not.toBeInTheDocument();
  });

  it("offers the wind-conditioned edge layer, off by default and switchable on", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NetworkMap />);
    const toggle = await screen.findByTestId("layer-toggle-windEdges");
    expect(toggle).toBeEnabled();
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    expect(toggle).toBeChecked();
    // The edge layer is drawn once enabled (empty of lines under jsdom, which has no
    // WebGL projection, but present as its own layer over the map).
    expect(await screen.findByTestId("wind-edge-layer")).toBeInTheDocument();
  });

  it("lets the available layer be switched off", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NetworkMap />);

    const toggle = await screen.findByTestId("layer-toggle-envStation");
    expect(toggle).toBeChecked();
    await user.click(toggle);
    expect(toggle).not.toBeChecked();
  });

  it("says the wind is unknown rather than showing a calm", async () => {
    renderWithProviders(<NetworkMap />);
    expect(await screen.findByTestId("wind-overlay-empty")).toHaveTextContent(/No wind readings/i);
  });

  it("shows the current wind when the network measured it", async () => {
    renderWithProviders(<NetworkMap />, {
      routes: { "/v1/readings": page(fixtures.windReadings) },
    });
    const overlay = await screen.findByTestId("wind-overlay");
    expect(overlay).toHaveAttribute("data-direction", "0");
    expect(within(overlay).getByText(/N 12.5 km\/h/)).toBeInTheDocument();
  });

  it("explains an empty network instead of showing a blank map", async () => {
    renderWithProviders(<NetworkMap />, { routes: { "/v1/stations": page([]) } });
    // The detail drawer carries its own "no station selected" empty state, so the
    // assertion is scoped to the map rather than to the page.
    const map = await screen.findByRole("region", { name: /network map/i });
    await waitFor(() => expect(within(map).getByTestId("empty-state")).toHaveTextContent(/make demo/));
  });

  it("explains a corpus whose stations carry no coordinates", async () => {
    renderWithProviders(<NetworkMap />, {
      routes: { "/v1/stations": page([fixtures.station({ lat: null, lon: null })]) },
    });
    const map = await screen.findByRole("region", { name: /network map/i });
    await waitFor(() =>
      expect(within(map).getByTestId("empty-state")).toHaveTextContent(/Location column/i),
    );
  });
});

describe("fetched street basemap", () => {
  it("builds a vector style over the local PMTiles archive, correctly credited", () => {
    const style = buildBasemapStyle("light");
    const source = style.sources.protomaps as { type: string; url: string; attribution: string };

    expect(source.type).toBe("vector");
    // The pmtiles protocol needs the archive's full location to range-read it.
    expect(source.url).toContain("pmtiles://");
    expect(source.url).toContain(LOCAL_BASEMAP_URL);
    // The open-stack pitch rests on OSM being credited.
    expect(source.attribution).toMatch(/OpenStreetMap/);
  });

  it("carries no symbol layers by default, so it needs no glyph fonts and stays offline", () => {
    for (const theme of ["dark", "light"] as const) {
      const style = buildBasemapStyle(theme);
      expect(style.layers.length).toBeGreaterThan(20);
      expect(style.layers.some((layer) => layer.type === "symbol")).toBe(false);
      // A symbol-free style must not declare a glyphs endpoint.
      expect(style.glyphs).toBeUndefined();
    }
  });

  it("keeps symbol layers and declares a glyphs endpoint once fonts are confirmed present (ADR 0011)", () => {
    for (const theme of ["dark", "light"] as const) {
      const style = buildBasemapStyle(theme, undefined, true);
      expect(style.layers.some((layer) => layer.type === "symbol")).toBe(true);
      expect(style.glyphs).toContain("/fonts/{fontstack}/{range}.pbf");
    }
  });

  it("re-themes: the dark and light basemaps differ", () => {
    const dark = JSON.stringify(buildBasemapStyle("dark"));
    const light = JSON.stringify(buildBasemapStyle("light"));
    expect(dark).not.toEqual(light);
  });

  it("uses only neutral basemap colours, so nothing competes with the state palette", () => {
    // Sentinel Green means verified and Trust Blue is the only interactive colour;
    // a saturated green or blue on the basemap would read as state. A neutral
    // grey/slate basemap keeps colour meaning what it means on the markers.
    const style = buildBasemapStyle("light");
    const fills = style.layers
      .map((layer) => {
        const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {};
        return (paint["background-color"] ?? paint["fill-color"] ?? paint["line-color"]) as unknown;
      })
      .filter((value): value is string => typeof value === "string" && value.startsWith("#"));

    expect(fills.length).toBeGreaterThan(0);
    for (const hex of fills) {
      const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      // Chroma (max-min) small => desaturated / neutral, whatever the brightness.
      const chroma = Math.max(...channels) - Math.min(...channels);
      expect(chroma, `${hex} is too saturated for a basemap`).toBeLessThanOrEqual(24);
    }
  });
});

describe("visibleStationLabels", () => {
  it("keeps every label when markers are spaced well apart", () => {
    const visible = visibleStationLabels([
      { stationId: "STA-01", x: 0, y: 0 },
      { stationId: "STA-02", x: 200, y: 0 },
      { stationId: "STA-03", x: 400, y: 0 },
    ]);
    expect(visible).toEqual(new Set(["STA-01", "STA-02", "STA-03"]));
  });

  it("hides a label whose offset box would overlap an already-placed one", () => {
    const visible = visibleStationLabels([
      { stationId: "STA-01", x: 0, y: 0 },
      { stationId: "STA-02", x: 5, y: 0 },
    ]);
    // Processed in station-id order: STA-01 is placed first and STA-02's box
    // collides with it, so only STA-01 keeps its label.
    expect(visible).toEqual(new Set(["STA-01"]));
  });

  it("shows both labels once they are far enough apart not to collide", () => {
    const visible = visibleStationLabels([
      { stationId: "STA-01", x: 0, y: 0 },
      { stationId: "STA-02", x: 200, y: 0 },
    ]);
    expect(visible).toEqual(new Set(["STA-01", "STA-02"]));
  });

  it("is independent of input order, so panning does not flip which label wins", () => {
    const a = visibleStationLabels([
      { stationId: "STA-01", x: 0, y: 0 },
      { stationId: "STA-02", x: 5, y: 0 },
    ]);
    const b = visibleStationLabels([
      { stationId: "STA-02", x: 5, y: 0 },
      { stationId: "STA-01", x: 0, y: 0 },
    ]);
    expect(a).toEqual(b);
  });
});

describe("probeBasemap", () => {
  const bytes = (text: string): Response =>
    ({ ok: true, arrayBuffer: async () => new TextEncoder().encode(text).buffer }) as Response;

  it("is false when the archive is absent (a 404)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));
    await expect(probeBasemap("/basemap/debrecen.pmtiles")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });

  it("is true only when the bytes are a real PMTiles archive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bytes("PMTiles\x03...")));
    await expect(probeBasemap("/basemap/debrecen.pmtiles")).resolves.toBe(true);
    vi.unstubAllGlobals();
  });

  it("is false on an SPA HTML fallback that answered 200 - the bug this guards", async () => {
    // The dev/preview server returns index.html with a 200 for any unknown path.
    // A HEAD or ok-only probe would call that "present" and the map would hang on
    // HTML it cannot parse as tiles.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bytes("<!doctype html><html>...")));
    await expect(probeBasemap("/basemap/debrecen.pmtiles")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });

  it("is false, not a throw, when the request fails entirely", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(probeBasemap("/basemap/debrecen.pmtiles")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });
});

describe("probeGlyphs", () => {
  const bytes = (...values: number[]): Response =>
    ({ ok: true, arrayBuffer: async () => new Uint8Array(values).buffer }) as Response;

  it("is false when the font file is absent (a 404)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));
    await expect(probeGlyphs("/fonts/Noto Sans Regular/0-255.pbf")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });

  it("is true only when the first byte is a real glyph PBF's protobuf tag", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bytes(0x0a, 0x88, 0xd2, 0x04)));
    await expect(probeGlyphs("/fonts/Noto Sans Regular/0-255.pbf")).resolves.toBe(true);
    vi.unstubAllGlobals();
  });

  it("is false on an SPA HTML fallback that answered 200 - the same bug probeBasemap guards", async () => {
    // "<" is 0x3c, not the glyph PBF's 0x0a tag byte.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bytes(0x3c, 0x21, 0x64, 0x6f)));
    await expect(probeGlyphs("/fonts/Noto Sans Regular/0-255.pbf")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });

  it("is false, not a throw, when the request fails entirely", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(probeGlyphs("/fonts/Noto Sans Regular/0-255.pbf")).resolves.toBe(false);
    vi.unstubAllGlobals();
  });
});

describe("basemap unavailability notice", () => {
  // MapLibre itself is stubbed under jsdom (src/test/maplibre-stub.ts) and never
  // throws, so the "MapLibre could not start" notice - a real no-WebGL browser
  // failure - is only reachable in the Playwright e2e, which drives a real GL
  // context. What jsdom *can* exercise is the other case: MapLibre running fine
  // while the tiles probe finds nothing, which is a plain fetch this suite controls.
  it("says the tiles were never fetched, not that the browser can't render", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));
    renderWithProviders(<NetworkMap />);

    await screen.findAllByTestId("station-marker");
    expect(await screen.findByTestId("basemap-unavailable-tiles")).toHaveTextContent(
      /make basemap/,
    );
    expect(screen.queryByTestId("basemap-unavailable-engine")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("shows neither notice once the tiles probe confirms the archive", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: async () => new TextEncoder().encode("PMTiles\x03...").buffer,
      } as Response),
    );
    renderWithProviders(<NetworkMap />);

    await screen.findAllByTestId("station-marker");
    await waitFor(() =>
      expect(screen.queryByTestId("basemap-unavailable-tiles")).not.toBeInTheDocument(),
    );
    expect(screen.queryByTestId("basemap-unavailable-engine")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});

describe("station labels", () => {
  it("names a marker with its station id, beside it rather than inside it", async () => {
    renderWithProviders(<NetworkMap />);
    const labels = await screen.findAllByTestId("station-label");
    // STA-01 and STA-02 share a latitude in the fixtures and the stub projection
    // places them 18px apart - closer than a label's own width - so this also
    // exercises the collision suppression: STA-02's label yields to STA-01's.
    expect(labels.map((label) => label.textContent)).toEqual(["STA-01", "STA-03"]);
    // The marker itself is never affected by a suppressed label.
    expect(screen.getByRole("button", { name: /STA-02/i })).toBeInTheDocument();
    // Decorative: the marker button already carries the station id in its
    // accessible name, so the label must not be announced a second time.
    for (const label of labels) expect(label).toHaveAttribute("aria-hidden", "true");
  });
});
