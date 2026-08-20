import type { ProvEvent, QualityStation, Station } from "../../api/client";
import { sortCodesBySeverity } from "../../api/reason-codes";
import { trustState, type TrustState } from "../../lib/trust";

/**
 * Turning the API's three separate answers into the markers the map draws.
 *
 * Pure functions, no React and no MapLibre, because this is the part that has to be
 * right: which station is which colour, which one carries an event glyph, and which
 * one has no score at all. The rendering is easy to look at and hard to test; this
 * is the reverse.
 */

export type LayerId = "envStation" | "trafficCounter" | "busStop" | "windEdges";

export interface LayerDefinition {
  id: LayerId;
  label: string;
  /** False for layers whose data arrives in a later phase. */
  available: boolean;
  /** Shown as the tooltip when a layer is not yet available. */
  unavailableReason?: string;
  defaultOn: boolean;
}

/**
 * The layer list.
 *
 * Wind-conditioned edges are built disabled with an explicit reason rather than
 * hidden, because an operator who can see the toggle understands the product's
 * shape - and because hiding it would let us quietly forget to build it. Traffic
 * counters and bus stops are the same: the Enclod and GTFS sources are ingested by
 * the phase-1 abstraction but are not part of the station trust surface yet.
 */
export const MAP_LAYERS: readonly LayerDefinition[] = [
  { id: "envStation", label: "EnvStation", available: true, defaultOn: true },
  {
    id: "trafficCounter",
    label: "TrafficCounter",
    available: false,
    unavailableReason: "Enclod counters are ingested but not yet placed on the map.",
    defaultOn: false,
  },
  {
    id: "busStop",
    label: "BusStop",
    available: false,
    unavailableReason: "GTFS stops are ingested but not yet placed on the map.",
    defaultOn: false,
  },
  {
    id: "windEdges",
    label: "Wind-conditioned edges",
    available: true,
    defaultOn: false,
  },
];

export interface StationMarker {
  stationId: string;
  name: string | null;
  lat: number;
  lon: number;
  zoneType: string | null;
  trust: number | null;
  state: TrustState;
  /** Sorted most-severe first; always at least one entry when a score exists. */
  reasonCodes: string[];
  flagCount: number;
  /** True when the station has an unadjudicated event in the current run. */
  hasActiveEvent: boolean;
  eventHeadline: string | null;
}

export interface BuildMarkersInput {
  stations: readonly Station[];
  quality: readonly QualityStation[];
  events: readonly ProvEvent[];
}

/**
 * Build the marker set.
 *
 * Stations without coordinates are excluded and counted separately rather than
 * dropped silently - a station missing from the map is a coverage fact the operator
 * needs told, not an absence to paper over.
 */
export function buildStationMarkers({ stations, quality, events }: BuildMarkersInput): {
  markers: StationMarker[];
  withoutCoordinates: string[];
} {
  const qualityById = new Map(quality.map((row) => [row.station_id, row]));
  const eventsById = new Map<string, ProvEvent>();
  for (const event of events) {
    // Events arrive ranked; keep the highest-ranked one per station.
    const existing = eventsById.get(event.station_id);
    if (!existing || event.rank < existing.rank) eventsById.set(event.station_id, event);
  }

  const markers: StationMarker[] = [];
  const withoutCoordinates: string[] = [];

  for (const station of stations) {
    if (typeof station.lat !== "number" || typeof station.lon !== "number") {
      withoutCoordinates.push(station.station_id);
      continue;
    }
    const row = qualityById.get(station.station_id);
    const event = eventsById.get(station.station_id);
    markers.push({
      stationId: station.station_id,
      name: station.name ?? null,
      lat: station.lat,
      lon: station.lon,
      zoneType: station.zone_type ?? null,
      trust: row?.trust ?? null,
      state: trustState(row?.trust ?? null),
      reasonCodes: sortCodesBySeverity(row?.reason_codes ?? []),
      flagCount: row?.flag_count ?? 0,
      hasActiveEvent: Boolean(event),
      eventHeadline: event?.headline ?? null,
    });
  }

  markers.sort((a, b) => a.stationId.localeCompare(b.stationId));
  withoutCoordinates.sort();
  return { markers, withoutCoordinates };
}

/** Counts per state, for the legend and the at-a-glance strip. */
export function summariseMarkers(markers: readonly StationMarker[]): Record<TrustState, number> {
  const counts: Record<TrustState, number> = { verified: 0, degraded: 0, fault: 0, unknown: 0 };
  for (const marker of markers) counts[marker.state] += 1;
  return counts;
}

// -------------------------------------------------------------------- wind
export const WIND_SPEED_PARAMETER = "Wind_Speed";
export const WIND_DIRECTION_PARAMETER = "Wind_Direction";

export interface WindVector {
  /** Metorological bearing the wind blows *from*, in degrees. */
  directionDegrees: number;
  speed: number;
  speedUnit: string;
  observedAt: string;
  /** How many stations the mean was taken over. */
  stationCount: number;
}

interface WindReadingLike {
  station_id: string;
  parameter: string;
  timestamp_utc: string;
  value: number | null;
  unit: string;
}

/**
 * The network's current wind, as a circular mean over the newest hour that has
 * readings.
 *
 * A plain arithmetic mean of bearings is wrong at the 360/0 wrap - 350 and 10
 * average to 180, pointing the arrow exactly backwards - so directions are averaged
 * as unit vectors. Returns null rather than a guess when no wind readings exist:
 * DEB-KER15 carries no wind sensors at all, and a network-wide absence has to read
 * as "no data", not as a calm.
 */
export function currentWind(readings: readonly WindReadingLike[]): WindVector | null {
  const directions = readings.filter(
    (r) => r.parameter === WIND_DIRECTION_PARAMETER && r.value !== null,
  );
  const speeds = readings.filter((r) => r.parameter === WIND_SPEED_PARAMETER && r.value !== null);
  if (directions.length === 0) return null;

  const latest = directions.reduce(
    (newest, r) => (r.timestamp_utc > newest ? r.timestamp_utc : newest),
    directions[0]!.timestamp_utc,
  );
  const atLatest = directions.filter((r) => r.timestamp_utc === latest);

  let sumX = 0;
  let sumY = 0;
  for (const reading of atLatest) {
    const radians = ((reading.value as number) * Math.PI) / 180;
    sumX += Math.cos(radians);
    sumY += Math.sin(radians);
  }
  const mean = (Math.atan2(sumY / atLatest.length, sumX / atLatest.length) * 180) / Math.PI;

  const speedsAtLatest = speeds.filter((r) => r.timestamp_utc === latest);
  const speedValues = speedsAtLatest.map((r) => r.value as number);
  const meanSpeed =
    speedValues.length > 0 ? speedValues.reduce((a, b) => a + b, 0) / speedValues.length : 0;

  return {
    directionDegrees: (mean + 360) % 360,
    speed: meanSpeed,
    speedUnit: speedsAtLatest[0]?.unit ?? "",
    observedAt: latest,
    stationCount: atLatest.length,
  };
}

const COMPASS = [
  "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
];

export function compassPoint(degrees: number): string {
  return COMPASS[Math.round((((degrees % 360) + 360) % 360) / 22.5) % 16] ?? "N";
}

// -------------------------------------------------------------------- labels

export interface ProjectedMarker {
  stationId: string;
  x: number;
  y: number;
}

/** The label's offset from the marker centre and its approximate glyph metrics,
 *  matched to the CSS in MapOverlays.tsx (`left-full ml-1`, `text-micro`). */
const LABEL_OFFSET_X = 12;
const LABEL_HEIGHT = 14;
const LABEL_CHAR_WIDTH = 6;
const LABEL_PADDING_X = 8;

/**
 * Which station labels can be shown without overlapping another one.
 *
 * Rather than a single hardcoded zoom cutoff, this measures the actual projected
 * screen boxes and greedily keeps the ones that do not collide - so labels declutter
 * correctly regardless of how the stations happen to be spaced at the fitted zoom,
 * and re-densify automatically once the operator zooms in past a real conflict.
 * Processed in station-id order so the result is deterministic and independent of
 * marker array order.
 */
export function visibleStationLabels(markers: readonly ProjectedMarker[]): ReadonlySet<string> {
  const ordered = [...markers].sort((a, b) => a.stationId.localeCompare(b.stationId));
  const placed: { x0: number; y0: number; x1: number; y1: number }[] = [];
  const visible = new Set<string>();

  for (const marker of ordered) {
    const width = marker.stationId.length * LABEL_CHAR_WIDTH + LABEL_PADDING_X;
    const x0 = marker.x + LABEL_OFFSET_X;
    const y0 = marker.y - LABEL_HEIGHT / 2;
    const x1 = x0 + width;
    const y1 = y0 + LABEL_HEIGHT;

    const collides = placed.some(
      (box) => x0 < box.x1 && x1 > box.x0 && y0 < box.y1 && y1 > box.y0,
    );
    if (collides) continue;
    placed.push({ x0, y0, x1, y1 });
    visible.add(marker.stationId);
  }

  return visible;
}
