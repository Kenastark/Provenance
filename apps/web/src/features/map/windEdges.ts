import type { WindVector } from "./stationMarkers";
import type { StationMarker } from "./stationMarkers";

/**
 * The wind-conditioned edges the map draws over the network.
 *
 * This is a deliberate, documented mirror of the backend's edge kernel
 * (`src/provenance/graph/edges.py`) — the directional dispersion-cone term and the
 * distance decay — computed client-side purely so the map can render *which*
 * neighbours sit downwind of each station under the current wind, and how strongly.
 * It is a visual aid, not the authority: the adjudicator's decision and its exact
 * weights come from the backend and are shown in the event evidence bundle. The
 * speed factor is dropped here because at one instant it scales every edge equally
 * and so does not change the picture; the constants below track graph.yaml's
 * provisional defaults and only need to agree in spirit, since nothing branches on
 * them.
 */

const SIGMA_ANGLE_DEG = 25;
const DISTANCE_DECAY_KM = 5;
const MAX_DISTANCE_KM = 15;
const MIN_WIND_SPEED = 0.1;
const WEIGHT_FLOOR = 0.05;
const EARTH_RADIUS_KM = 6371.0088;

export interface WindEdge {
  srcId: string;
  dstId: string;
  weight: number;
  srcLat: number;
  srcLon: number;
  dstLat: number;
  dstLon: number;
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dPhi = toRad(lat2 - lat1);
  const dLambda = toRad(lon2 - lon1);
  const a =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function initialBearingDeg(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLambda = toRad(lon2 - lon1);
  const y = Math.sin(dLambda) * Math.cos(toRad(lat2));
  const x =
    Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
    Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLambda);
  return (((Math.atan2(y, x) * 180) / Math.PI) + 360) % 360;
}

/** Wrapped separation between two bearings, in [0, 180]°. Correct across the 0/360 seam. */
export function angularDifferenceDeg(a: number, b: number): number {
  // JS `%` keeps the sign of the dividend, so a plain `(a - b + 180) % 360` goes
  // negative and breaks the wrap; normalise into [0, 360) first.
  const wrapped = ((((a - b + 180) % 360) + 360) % 360) - 180;
  return Math.abs(wrapped);
}

/**
 * The directed display weight of the i→j edge under the current wind.
 *
 * `wind.directionDegrees` is the bearing the wind blows *from*; the air travels
 * toward `from + 180`, and an edge points where the plume would go.
 */
export function edgeWeight(
  srcLat: number,
  srcLon: number,
  dstLat: number,
  dstLon: number,
  wind: WindVector,
): number {
  if (wind.speed < MIN_WIND_SPEED) return 0;
  const dist = haversineKm(srcLat, srcLon, dstLat, dstLon);
  if (dist > MAX_DISTANCE_KM) return 0;
  const bearing = initialBearingDeg(srcLat, srcLon, dstLat, dstLon);
  const travel = (wind.directionDegrees + 180) % 360;
  const delta = angularDifferenceDeg(bearing, travel);
  const directional = Math.exp(-delta / SIGMA_ANGLE_DEG);
  const decay = Math.exp(-dist / DISTANCE_DECAY_KM);
  return directional * decay;
}

/** Every downwind edge worth drawing, strongest first. */
export function computeWindEdges(
  markers: readonly StationMarker[],
  wind: WindVector | null,
): WindEdge[] {
  if (!wind || wind.speed < MIN_WIND_SPEED) return [];
  const edges: WindEdge[] = [];
  for (const src of markers) {
    for (const dst of markers) {
      if (src.stationId === dst.stationId) continue;
      const weight = edgeWeight(src.lat, src.lon, dst.lat, dst.lon, wind);
      if (weight < WEIGHT_FLOOR) continue;
      edges.push({
        srcId: src.stationId,
        dstId: dst.stationId,
        weight,
        srcLat: src.lat,
        srcLon: src.lon,
        dstLat: dst.lat,
        dstLon: dst.lon,
      });
    }
  }
  edges.sort((a, b) => b.weight - a.weight);
  return edges;
}
