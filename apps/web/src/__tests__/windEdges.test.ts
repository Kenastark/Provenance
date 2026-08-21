import { describe, expect, it } from "vitest";
import type { StationMarker, WindVector } from "../features/map/stationMarkers";
import {
  angularDifferenceDeg,
  attentionEdgesFromOverlay,
  computeWindEdges,
  edgeWeight,
  initialBearingDeg,
} from "../features/map/windEdges";

const SRC = { lat: 47.53, lon: 21.55 };
const EAST = { lat: 47.53, lon: 21.59 };
const NORTH = { lat: 47.57, lon: 21.55 };

function wind(directionDegrees: number, speed = 5): WindVector {
  return { directionDegrees, speed, speedUnit: "m/s", observedAt: "", stationCount: 1 };
}

function marker(id: string, lat: number, lon: number): StationMarker {
  return {
    stationId: id,
    name: id,
    lat,
    lon,
    zoneType: null,
    trust: 1,
    state: "verified",
    reasonCodes: [],
    flagCount: 0,
    hasActiveEvent: false,
    eventHeadline: null,
    provenance: "measured",
  };
}

describe("wind-edge geometry (map mirror)", () => {
  it("wraps angular difference across the 0/360 seam", () => {
    expect(angularDifferenceDeg(359, 1)).toBeCloseTo(2);
    expect(angularDifferenceDeg(10, 350)).toBeCloseTo(20);
  });

  it("bears due east for an eastward step", () => {
    expect(initialBearingDeg(SRC.lat, SRC.lon, EAST.lat, EAST.lon)).toBeCloseTo(90, 0);
  });

  it("is maximal downwind and near-zero crosswind", () => {
    // Wind from the west (270°) carries a plume east; EAST is downwind, NORTH is not.
    const downwind = edgeWeight(SRC.lat, SRC.lon, EAST.lat, EAST.lon, wind(270));
    const crosswind = edgeWeight(SRC.lat, SRC.lon, NORTH.lat, NORTH.lon, wind(270));
    expect(downwind).toBeGreaterThan(crosswind);
    expect(crosswind).toBeLessThan(0.1 * downwind);
  });

  it("collapses to zero in a calm", () => {
    expect(edgeWeight(SRC.lat, SRC.lon, EAST.lat, EAST.lon, wind(270, 0))).toBe(0);
  });

  it("draws downwind edges only, strongest first", () => {
    const markers = [marker("SRC", SRC.lat, SRC.lon), marker("E", EAST.lat, EAST.lon), marker("N", NORTH.lat, NORTH.lon)];
    const edges = computeWindEdges(markers, wind(270));
    // SRC→E is downwind; the reverse and crosswind links fall below the floor.
    expect(edges.some((e) => e.srcId === "SRC" && e.dstId === "E")).toBe(true);
    expect(edges.every((e) => e.weight >= 0)).toBe(true);
    for (let i = 1; i < edges.length; i += 1) {
      expect(edges[i - 1]!.weight).toBeGreaterThanOrEqual(edges[i]!.weight);
    }
  });

  it("returns nothing without wind", () => {
    const markers = [marker("SRC", SRC.lat, SRC.lon), marker("E", EAST.lat, EAST.lon)];
    expect(computeWindEdges(markers, null)).toEqual([]);
  });
});

describe("attentionEdgesFromOverlay (learned overlay geometry)", () => {
  const markers = [marker("SRC", SRC.lat, SRC.lon), marker("E", EAST.lat, EAST.lon)];

  it("resolves each edge's station ids against the mapped markers' real coordinates", () => {
    const edges = attentionEdgesFromOverlay(
      { wind_conditioned: [{ src: "SRC", dst: "E", attention: 0.7 }] },
      markers,
    );
    expect(edges).toEqual([
      {
        srcId: "SRC",
        dstId: "E",
        relation: "wind_conditioned",
        attention: 0.7,
        srcLat: SRC.lat,
        srcLon: SRC.lon,
        dstLat: EAST.lat,
        dstLon: EAST.lon,
      },
    ]);
  });

  it("drops an edge naming a station the map cannot place, rather than drawing it at the origin", () => {
    const edges = attentionEdgesFromOverlay(
      { wind_conditioned: [{ src: "SRC", dst: "GHOST", attention: 0.9 }] },
      markers,
    );
    expect(edges).toEqual([]);
  });

  it("flattens every relation into one list, strongest attention first", () => {
    const edges = attentionEdgesFromOverlay(
      {
        wind_conditioned: [{ src: "SRC", dst: "E", attention: 0.3 }],
        spatial_proximity: [{ src: "E", dst: "SRC", attention: 0.8 }],
      },
      markers,
    );
    expect(edges.map((e) => e.relation)).toEqual(["spatial_proximity", "wind_conditioned"]);
    for (let i = 1; i < edges.length; i += 1) {
      expect(edges[i - 1]!.attention).toBeGreaterThanOrEqual(edges[i]!.attention);
    }
  });

  it("returns nothing for an empty overlay", () => {
    expect(attentionEdgesFromOverlay({}, markers)).toEqual([]);
  });
});
