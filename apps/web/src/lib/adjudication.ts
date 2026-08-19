/**
 * Reading the adjudication evidence bundle off an event.
 *
 * The backend stores the whole bundle under `event.evidence.adjudication` (the audit
 * left `evidence` a free-form JSON map, so no contract change was needed when
 * adjudication landed). `evidence` therefore arrives typed as `unknown`, and this is
 * the one place that turns it into something the UI can render — defensively, so a
 * missing or malformed bundle yields `null` and the screen falls back to "pending"
 * rather than throwing. Nothing here computes a verdict; it only parses one.
 */

export interface AdjudicationNeighbour {
  stationId: string;
  distanceKm: number;
  bearingDeg: number;
  edgeWeight: number;
  expectedExcess: number;
  actualExcess: number | null;
  corroborated: boolean;
  windProvenance: string;
}

export interface AdjudicationSeries {
  timestamps: string[];
  expected: number[];
  actual: (number | null)[];
}

export interface AdjudicationCovariate {
  name: string;
  state: string;
  reason: string;
}

export interface AdjudicationView {
  verdict: string;
  confidence: number;
  confidenceBand: string;
  routesToReview: boolean;
  matchScore: number;
  nDownwind: number;
  nUsable: number;
  reasonCodes: string[];
  wind: {
    fromDeg: number | null;
    toDeg: number | null;
    speed: number | null;
    speedUnit: string;
    provenance: string;
  };
  neighbours: AdjudicationNeighbour[];
  series: AdjudicationSeries;
  covariates: AdjudicationCovariate[];
  notes: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function numOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

/** Parse `event.evidence.adjudication`, or `null` if there is no valid bundle. */
export function parseAdjudication(evidence: unknown): AdjudicationView | null {
  if (!isRecord(evidence)) return null;
  const root = evidence.adjudication;
  if (!isRecord(root)) return null;
  const bundle = root.evidence;
  if (!isRecord(bundle)) return null;

  const verdict = str(root.verdict);
  if (!verdict) return null;

  const wind = isRecord(bundle.wind) ? bundle.wind : {};
  const neighboursRaw = Array.isArray(bundle.downwind_neighbours)
    ? bundle.downwind_neighbours
    : [];
  const seriesRaw = isRecord(bundle.series) ? bundle.series : {};
  const covariatesRaw = Array.isArray(bundle.covariates) ? bundle.covariates : [];

  const neighbours: AdjudicationNeighbour[] = neighboursRaw.filter(isRecord).map((n) => ({
    stationId: str(n.station_id),
    distanceKm: num(n.distance_km),
    bearingDeg: num(n.bearing_deg),
    edgeWeight: num(n.edge_weight),
    expectedExcess: num(n.expected_excess),
    actualExcess: numOrNull(n.actual_excess),
    corroborated: n.corroborated === true,
    windProvenance: str(n.wind_provenance),
  }));

  const series: AdjudicationSeries = {
    timestamps: Array.isArray(seriesRaw.timestamps) ? seriesRaw.timestamps.map((t) => str(t)) : [],
    expected: Array.isArray(seriesRaw.expected) ? seriesRaw.expected.map((v) => num(v)) : [],
    actual: Array.isArray(seriesRaw.actual) ? seriesRaw.actual.map((v) => numOrNull(v)) : [],
  };

  const covariates: AdjudicationCovariate[] = covariatesRaw.filter(isRecord).map((c) => ({
    name: str(c.name),
    state: str(c.state),
    reason: str(c.reason),
  }));

  return {
    verdict,
    confidence: num(root.confidence),
    confidenceBand: str(root.confidence_band),
    routesToReview: root.routes_to_review === true,
    matchScore: num(bundle.match_score),
    nDownwind: num(bundle.n_downwind),
    nUsable: num(bundle.n_usable),
    reasonCodes: Array.isArray(bundle.reason_codes) ? bundle.reason_codes.map((c) => str(c)) : [],
    wind: {
      fromDeg: numOrNull(wind.from_deg),
      toDeg: numOrNull(wind.to_deg),
      speed: numOrNull(wind.speed),
      speedUnit: str(wind.speed_unit),
      provenance: str(wind.provenance),
    },
    neighbours,
    series,
    covariates,
    notes: Array.isArray(bundle.notes) ? bundle.notes.map((n) => str(n)) : [],
  };
}
