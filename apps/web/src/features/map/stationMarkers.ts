import type {
  AttentionOverlay,
  BusStop,
  ProvEvent,
  QualityStation,
  ReferenceCounters,
  ReferenceStops,
  Station,
  TrafficCounter,
} from "../../api/client";
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

export type LayerId = "envStation" | "trafficCounter" | "busStop" | "windEdges" | "attentionOverlay";

/** "measured" = real, observed coordinates. "provisional" would mean a placeholder
 * - the map never draws that kind (see graph/topology.py's synthetic-provisional
 * graph nodes, which are a message-passing concern and never reach the basemap).
 * The type exists so a future layer cannot add a point to the canvas without
 * declaring which one it is. */
export type MarkerProvenance = "measured" | "provisional";

export interface LayerDefinition {
  id: LayerId;
  label: string;
  /** False until the layer's code path AND its source data both exist. */
  available: boolean;
  /** Shown as the tooltip when a layer is not available. */
  unavailableReason?: string;
  defaultOn: boolean;
}

/**
 * The static layer list.
 *
 * Wind-conditioned edges are built disabled with an explicit reason rather than
 * hidden, because an operator who can see the toggle understands the product's
 * shape - and because hiding it would let us quietly forget to build it.
 *
 * TrafficCounter and BusStop start disabled with a "checking" reason: their real
 * availability depends on whether the Enclod/GTFS drop is present, which is a
 * runtime fact from `/v1/reference/*`, not something this static list can know.
 * `resolveMapLayers` below overlays that answer once it arrives.
 */
export const MAP_LAYERS: readonly LayerDefinition[] = [
  { id: "envStation", label: "EnvStation", available: true, defaultOn: true },
  {
    id: "trafficCounter",
    label: "TrafficCounter",
    available: false,
    unavailableReason: "Checking whether Enclod counter coordinates are loaded…",
    defaultOn: false,
  },
  {
    id: "busStop",
    label: "BusStop",
    available: false,
    unavailableReason: "Checking whether the GTFS bundle is loaded…",
    defaultOn: false,
  },
  {
    id: "windEdges",
    label: "Wind-conditioned edges",
    available: true,
    defaultOn: false,
  },
  {
    id: "attentionOverlay",
    // Deliberately not "edges" or anything that echoes windEdges' label - this is a
    // learned claim, not the analytic wind kernel, and the two must never be mistaken
    // for each other at a glance (see AttentionEdgeLayer's dashed styling).
    label: "Learned attention (HST-GAT)",
    available: false,
    unavailableReason: "Checking whether the HST-GAT has been trained…",
    defaultOn: false,
  },
];

const BUS_STOPS_UNAVAILABLE_REASON =
  "GTFS bundle not loaded (data/raw/gtfs). Bus stops are ingested but there is nothing to place on the map yet.";
const TRAFFIC_COUNTERS_UNAVAILABLE_REASON =
  "Enclod counters carry no coordinates in this drop; the graph's counter nodes are provisional placeholders and are not drawn on the map.";
const ATTENTION_CHECKING_REASON = "Checking whether the HST-GAT has been trained…";

/**
 * Overlay the live reference-endpoint answers onto the static layer list.
 *
 * `undefined` for a query means "still loading" and is treated as unavailable
 * with a neutral reason - never optimistically enabled, because a toggle that
 * flips available then snaps back to disabled reads as a bug rather than a
 * coverage fact. The attention overlay is the one exception once its query has
 * settled: the API's own `reason` (e.g. "has not been trained") is more honest
 * than a generic placeholder, and standing rule 6 asks for exactly that sentence
 * on the toggle's tooltip.
 */
export function resolveMapLayers(
  base: readonly LayerDefinition[],
  runtime: {
    busStops: ReferenceStops | undefined;
    trafficCounters: ReferenceCounters | undefined;
    attentionOverlay: AttentionOverlay | undefined;
  },
): LayerDefinition[] {
  return base.map((layer) => {
    if (layer.id === "busStop") {
      const available = runtime.busStops?.available ?? false;
      return { ...layer, available, unavailableReason: available ? undefined : BUS_STOPS_UNAVAILABLE_REASON };
    }
    if (layer.id === "trafficCounter") {
      const available = runtime.trafficCounters?.available ?? false;
      return {
        ...layer,
        available,
        unavailableReason: available ? undefined : TRAFFIC_COUNTERS_UNAVAILABLE_REASON,
      };
    }
    if (layer.id === "attentionOverlay") {
      const overlay = runtime.attentionOverlay;
      const available = overlay?.available ?? false;
      return {
        ...layer,
        available,
        unavailableReason: available ? undefined : (overlay?.reason ?? ATTENTION_CHECKING_REASON),
      };
    }
    return layer;
  });
}

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
  /** Always "measured": a station without real coordinates is excluded, not
   * placed provisionally (see `withoutCoordinates` below). */
  provenance: MarkerProvenance;
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
      provenance: "measured",
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

// ---------------------------------------------------------- reference layers
// Bus stops and traffic counters carry no trust score and no reason code - they
// are context, not the trust surface - so they get a subordinate marker class
// deliberately outside the trust palette (Sentinel Green means "verified
// reading" and must never label a bus stop or a counter).

export interface BusStopMarker {
  stopId: string;
  lat: number;
  lon: number;
  nRoutes: number;
  provenance: MarkerProvenance;
}

/** Real GTFS stops only - the endpoint already refuses to answer when the
 * bundle is absent, so every stop that reaches here is a measured coordinate. */
export function buildBusStopMarkers(stops: readonly BusStop[]): BusStopMarker[] {
  return stops
    .map((s) => ({ stopId: s.stop_id, lat: s.lat, lon: s.lon, nRoutes: s.n_routes, provenance: "measured" as const }))
    .sort((a, b) => a.stopId.localeCompare(b.stopId));
}

export interface TrafficCounterMarker {
  counterId: string;
  name: string;
  lat: number;
  lon: number;
  provenance: MarkerProvenance;
}

/** Real Enclod counter coordinates only - see counter_locations() in
 * io/ingest/enclod.py: these are the observed uuid/nick/lat/lng columns, never
 * the graph's synthetic-provisional placeholder nodes. */
export function buildTrafficCounterMarkers(counters: readonly TrafficCounter[]): TrafficCounterMarker[] {
  return counters
    .map((c) => ({
      counterId: c.counter_id,
      name: c.name,
      lat: c.lat,
      lon: c.lon,
      provenance: "measured" as const,
    }))
    .sort((a, b) => a.counterId.localeCompare(b.counterId));
}

// -------------------------------------------------------------------- wind
export const WIND_SPEED_PARAMETER = "Wind_Speed";
export const WIND_DIRECTION_PARAMETER = "Wind_Direction";
/** How far back from the anchor to look for a wind reading. "Current wind" is a
 * latest-sample readout, not a windowed series, so this is independent of whatever
 * macro time window (24h/7d/corpus) the operator has selected elsewhere - a few
 * cadence periods of slack is enough to survive a missed hour without pulling in
 * enough history, across every wind-carrying station, to risk the 200-row page cap
 * silently truncating before it reaches the newest readings (list_readings orders
 * ascending, oldest first). */
export const WIND_LOOKBACK_HOURS = 6;

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
