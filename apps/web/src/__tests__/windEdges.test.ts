import { describe, expect, it } from "vitest";
import type { StationMarker, WindVector } from "../features/map/stationMarkers";
import {
  angularDifferenceDeg,
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
