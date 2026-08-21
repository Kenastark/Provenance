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

/** One edge of the HST-GAT's learned attention, resolved to real coordinates. */
export interface AttentionEdge {
  srcId: string;
  dstId: string;
  /** The relation the model computed this weight over (e.g. "wind_conditioned"). */
  relation: string;
  /** Softmax weight over the destination's incoming edges of this relation, in [0, 1]. */
  attention: number;
  srcLat: number;
  srcLon: number;
  dstLat: number;
  dstLon: number;
}

/**
 * Turn the API's attention-overlay edges into drawable edges.
 *
 * The overlay carries station ids and a weight, not coordinates - this resolves each
 * id against the current markers, the same lookup the analytic wind edges are drawn
 * from, so the learned layer can never drift from the analytic one geometrically. An
 * edge naming a station the map cannot place (no coordinates) is dropped rather than
 * drawn at the origin.
 */
export function attentionEdgesFromOverlay(
  relations: Readonly<
    Record<string, readonly { src: string; dst: string; attention: number }[]>
  >,
  markers: readonly StationMarker[],
): AttentionEdge[] {
  const byId = new Map(markers.map((marker) => [marker.stationId, marker]));
  const edges: AttentionEdge[] = [];
  for (const [relation, relationEdges] of Object.entries(relations)) {
    for (const edge of relationEdges) {
      const src = byId.get(edge.src);
      const dst = byId.get(edge.dst);
      if (!src || !dst) continue;
      edges.push({
        srcId: edge.src,
        dstId: edge.dst,
        relation,
        attention: edge.attention,
        srcLat: src.lat,
        srcLon: src.lon,
        dstLat: dst.lat,
        dstLon: dst.lon,
      });
    }
  }
  edges.sort((a, b) => b.attention - a.attention);
  return edges;
}
