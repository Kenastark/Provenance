import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { NetworkMap } from "../features/map/NetworkMap";
import {
  buildStationMarkers,
  compassPoint,
  currentWind,
  summariseMarkers,
} from "../features/map/stationMarkers";
import { boundsForStations, buildFallbackStyle, graticule } from "../features/map/mapStyle";
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

  it("builds the graph-edge toggle disabled, with a reason", async () => {
    renderWithProviders(<NetworkMap />);
    const toggle = await screen.findByTestId("layer-toggle-windEdges");
    expect(toggle).toBeDisabled();
    expect(screen.getByText(/Available in graph view/i)).toBeInTheDocument();
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
