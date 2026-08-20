import type {
  AuditRun,
  BusStop,
  Defect,
  DeweatherSeries,
  Explain,
  ProvEvent,
  QualityStation,
  QualitySummary,
  Reading,
  ReferenceCounters,
  ReferenceStops,
  Station,
  TrafficCounter,
  TrustScore,
  Version,
} from "../api/client";

/**
 * Test fixtures shaped exactly like the API's responses.
 *
 * Deliberately hand-built rather than recorded, and deliberately small: these
 * describe the *shapes and edge cases* the UI has to survive - a station with no
 * coordinates, a station with no score, a coverage code that must not read as a
 * defect, a placeholder trust component. The numbers are illustrative and are never
 * asserted as facts about the real network; the numbers that matter come from the
 * audit engine and are covered by the Python suite's golden ledger.
 */

export const station = (overrides: Partial<Station> = {}): Station => ({
  station_id: "STA-01",
  name: "Synthetic site STA-01",
  lat: 47.577175,
  lon: 21.502204,
  zone_type: "urban",
  coverage: { PM10: 336, "PM2.5": 336, CO2: 331, NO: 336 },
  ...overrides,
});

export const stations: Station[] = [
  station(),
  station({ station_id: "STA-02", lat: 47.577175, lon: 21.520204, zone_type: "suburban" }),
  station({ station_id: "STA-03", lat: 47.559175, lon: 21.502204, zone_type: "industrial" }),
  // No coordinates: must be reported as unmapped, never dropped silently.
  station({ station_id: "STA-04", lat: null, lon: null, zone_type: null }),
];

export const busStop = (overrides: Partial<BusStop> = {}): BusStop => ({
  stop_id: "S-STA-01-0",
  lat: 47.5775,
  lon: 21.5025,
  n_routes: 3,
  ...overrides,
});

/** No GTFS bundle loaded - the honest default a fresh clone actually reports. */
export const referenceStopsUnavailable: ReferenceStops = { available: false, stops: [] };
export const referenceStopsAvailable: ReferenceStops = {
  available: true,
  stops: [busStop(), busStop({ stop_id: "S-STA-02-0", lat: 47.5772, lon: 21.5203 })],
};

export const trafficCounter = (overrides: Partial<TrafficCounter> = {}): TrafficCounter => ({
  counter_id: "gh9d5GPy764KFLjmCrjnbG",
  name: "47.towards.Debrecen.far.IN",
  lat: 47.4607,
  lon: 21.6366,
  ...overrides,
});

/** No Enclod archive found - the honest default a fresh clone actually reports. */
export const referenceCountersUnavailable: ReferenceCounters = { available: false, counters: [] };
export const referenceCountersAvailable: ReferenceCounters = {
  available: true,
  counters: [trafficCounter(), trafficCounter({ counter_id: "RbuHQFeNkxcPagEZdwc4PH", name: "BMW körút" })],
};

export const trustComponents = [
  {
    name: "HealthConf",
    value: 0.42,
    weight: 0.4,
    contribution: 0.168,
    is_placeholder: false,
    detail: "7 active flags",
    evidence: { n_defects: 7 },
  },
  {
    name: "ImputationCertainty",
    value: 0.88,
    weight: 0.2,
    contribution: 0.176,
    is_placeholder: true,
    detail: "imputation uncertainty 12.0% (placeholder, no model)",
    evidence: { pct: 12.0 },
  },
  {
    name: "CrossSensorConsistency",
    value: 0.61,
    weight: 0.2,
    contribution: 0.122,
    is_placeholder: false,
    detail: "3 parameter(s) compared to peers",
    evidence: { n: 4, min_peers: 2 },
  },
  {
    name: "PhysicalPlausibility",
    value: 0.2,
    weight: 0.2,
    contribution: 0.04,
    is_placeholder: false,
    detail: "worst-case margin over 336 readings",
    evidence: { n_readings: 336 },
  },
];

export const trustScore = (overrides: Partial<TrustScore> = {}): TrustScore => ({
  station_id: "STA-01",
  timestamp_utc: "2026-05-14T00:00:00",
  trust: 0.51,
  components: trustComponents,
  // Every placeholder-bearing trust code, so the fixture proves each one renders
  // as a sentence rather than as a template.
  reason_codes: ["T01", "T04", "T02", "T03"],
  risk: {
    value: 0.31,
    trust: 0.51,
    severity_vs_threshold: 0.4,
    population_exposure: 0.5,
    population_exposure_stubbed: true,
  },
  degraded: false,
  notes: ["ImputationUncertainty is a placeholder term (12.0% absent); no model yet."],
  evidence: { n_defects: 7, pct: 12.0, n: 4, min_peers: 2, n_readings: 336 },
  ...overrides,
});

export const qualityStation = (overrides: Partial<QualityStation> = {}): QualityStation => ({
  station_id: "STA-01",
  zone_type: "urban",
  health: 0.42,
  trust: 0.51,
  flag_count: 7,
  n_parameters: 4,
  last_reading_at: "2026-05-14T23:00:00",
  components: trustComponents,
  reason_codes: ["T01", "T04"],
  evidence: { n_defects: 7, pct: 12.0, n: 4, min_peers: 2, n_readings: 336 },
  ...overrides,
});

export const qualitySummary: QualitySummary = {
  audit_run_id: "run-2026-05-15",
  stations: [
    qualityStation(),
    qualityStation({ station_id: "STA-02", trust: 0.93, health: 0.98, flag_count: 0, reason_codes: ["T00"] }),
    qualityStation({ station_id: "STA-03", trust: 0.22, health: 0.15, flag_count: 31, reason_codes: ["T04", "T01"] }),
    // Never scored: must render as "not scored", not as a red fault.
    qualityStation({ station_id: "STA-04", trust: null, health: null, flag_count: 0, reason_codes: [] }),
  ],
};

export const auditRun = (overrides: Partial<AuditRun> = {}): AuditRun => ({
  id: "run-2026-05-15",
  code_version: "0.3.0",
  config_hash: "cfg0123456789abcdef",
  data_checksum: "dat0123456789abcdef",
  generated_at: "2026-05-15T00:00:00",
  n_rows: 4032,
  n_defective_cells: 812,
  n_covered_cells: 4020,
  defect_rate: 0.20199,
  conventional_completeness_pct: 99.95,
  ingest_batch_id: "batch-1",
  ...overrides,
});

/**
 * The stored run summary, as the engine writes it.
 *
 * `defects_by_code` is computed by the audit over *every* row. The dashboard must
 * read it rather than counting the paginated ledger, which stops at 500.
 */
export const auditRunDetail = {
  run: auditRun(),
  summary: {
    defect_rate: { n_defective_cells: 812, n_covered_cells: 4020, rate: 0.20199 },
    defects_by_code: { R07: 3, R09: 4, R10: 336, R12: 336, R18: 1 },
  } as Record<string, unknown>,
};

export const defect = (overrides: Partial<Defect> = {}): Defect => ({
  id: 1,
  audit_run_id: "run-2026-05-15",
  reason_code: "R07",
  station_id: "STA-03",
  parameter: "PM10",
  timestamp_utc: "2026-05-01T12:00:00",
  severity: "critical",
  counts_toward_rate: true,
  evidence: { value: 3000, unit: "µg/m3", parameter: "PM10", max: 2000 },
  ...overrides,
});

export const defects: Defect[] = [
  defect(),
  defect({
    id: 2,
    reason_code: "R09",
    station_id: "STA-01",
    parameter: "PM2.5",
    severity: "critical",
    evidence: { pm25: 41.2, pm10: 38.0 },
  }),
  // A coverage fact: excluded from the defect rate, must not read as a fault.
  defect({
    id: 3,
    reason_code: "R18",
    station_id: "STA-03",
    parameter: "NO",
    severity: "info",
    counts_toward_rate: false,
    evidence: { parameter: "NO" },
  }),
];

export const provEvent = (overrides: Partial<ProvEvent> = {}): ProvEvent => ({
  id: 1,
  audit_run_id: "run-2026-05-15",
  rank: 1,
  category: "physical",
  reason_code: "R07",
  station_id: "STA-03",
  parameter: "PM10",
  timestamp_utc: "2026-05-01T12:00:00",
  headline: "PM10 at 3000 µg/m3, above the physical maximum",
  severity: "critical",
  evidence: { value: 3000, unit: "µg/m3", parameter: "PM10" },
  verdict: null,
  ...overrides,
});

export const events: ProvEvent[] = [
  // Both sit inside the default 7-day window (anchored on the audit run's
  // generated_at, 2026-05-15). Window filtering has its own test; these exist to
  // exercise rendering.
  provEvent({ timestamp_utc: "2026-05-10T12:00:00" }),
  provEvent({
    id: 2,
    rank: 2,
    category: "statistical",
    reason_code: "R12",
    station_id: "STA-01",
    parameter: "WaterLevel",
    timestamp_utc: "2026-05-13T00:00:00",
    headline: "WaterLevel frozen for the whole record",
    severity: "high",
    evidence: { duration: "336 h" },
  }),
];

export const reading = (overrides: Partial<Reading> = {}): Reading => ({
  station_id: "STA-01",
  parameter: "PM10",
  timestamp_utc: "2026-05-01T00:00:00",
  value: 30,
  unit: "µg/m3",
  instrument_id: null,
  source_file: "STA-01_air.csv",
  row_hash: "hash-0",
  reason_codes: [],
  ...overrides,
});

/** A short series with one gap and one flagged point. */
export const readings: Reading[] = Array.from({ length: 12 }, (_, index) =>
  reading({
    timestamp_utc: `2026-05-01T${String(index).padStart(2, "0")}:00:00`,
    value: index === 5 ? null : 28 + index,
    row_hash: `hash-${index}`,
    reason_codes: index === 8 ? ["R07"] : [],
  }),
);

export const version: Version = {
  version: "0.3.0",
  git_sha: "abcdef1234567890",
  config_hash: "cfg0123456789abcdef",
  trust_config_hash: "trust0123456789",
  model_versions: { trust_score: "v1" },
};

export const windReadings: Reading[] = [
  reading({
    parameter: "Wind_Direction",
    timestamp_utc: "2026-05-14T23:00:00",
    value: 350,
    unit: "degrees",
    row_hash: "wd-1",
  }),
  reading({
    station_id: "STA-02",
    parameter: "Wind_Direction",
    timestamp_utc: "2026-05-14T23:00:00",
    value: 10,
    unit: "degrees",
    row_hash: "wd-2",
  }),
  reading({
    parameter: "Wind_Speed",
    timestamp_utc: "2026-05-14T23:00:00",
    value: 12.5,
    unit: "km/h",
    row_hash: "ws-1",
  }),
];

// A model-backed SHAP explanation for defect 1 (STA-03 · PM10). The attributions plus
// the base value reconstruct the prediction; the sign of each drives the bar direction.
export const explain: Explain = {
  defect_id: 1,
  station_id: "STA-03",
  parameter: "PM10",
  timestamp_utc: "2026-05-14T12:00:00",
  reason_code: "R07",
  method: "model",
  fault_class: "physically_impossible",
  predicted_class: null,
  sentence:
    "Driven primarily by the shallow overnight mixing layer (lowered), then wind speed (raised) and humidity (lowered); not day of week.",
  degraded: false,
  model_versions: { deweather: "v1-abc12345", fault: "v1-def67890" },
  base_value: 42.1,
  prediction: 39.4,
  residual: 2960.6,
  reconstructs: true,
  attributions: [
    { feature: "boundary_layer_proxy", value: -6.2, feature_value: 0.4, provenance: "proxy" },
    { feature: "wind_speed", value: 3.1, feature_value: 8.0, provenance: "measured" },
    { feature: "humidity", value: -1.4, feature_value: 60.0, provenance: "measured" },
    { feature: "hour_sin", value: 0.8, feature_value: 0.5, provenance: "derived" },
    { feature: "temperature", value: 0.2, feature_value: 18.0, provenance: "weather_feed" },
  ],
  notes: [],
};

// The degraded explanation the API returns when no model artefact is loaded.
export const explainDegraded: Explain = {
  ...explain,
  method: "degraded",
  degraded: true,
  fault_class: null,
  sentence: "Value of 3000 µg/m3 exceeds the physical maximum for PM10.",
  base_value: null,
  prediction: null,
  residual: null,
  reconstructs: null,
  attributions: [],
  model_versions: {},
  notes: ["No model artefact was available; this explanation comes from the statistics layer alone."],
};

// A stored deweathered series for STA-03 · PM10: raw vs weather-predicted vs residual.
export const deweatherSeries: DeweatherSeries = {
  station_id: "STA-03",
  parameter: "PM10",
  model_version: "v1-abc12345",
  degraded: false,
  series: Array.from({ length: 12 }, (_, index) => {
    const actual = 30 + 8 * Math.sin(index / 2);
    const predicted = 30 + 6 * Math.sin(index / 2);
    return {
      timestamp_utc: `2026-05-14T${String(index).padStart(2, "0")}:00:00`,
      actual,
      predicted,
      residual: actual - predicted,
    };
  }),
};

export const deweatherDegraded: DeweatherSeries = {
  station_id: "STA-03",
  parameter: "PM10",
  model_version: null,
  degraded: true,
  series: [],
};
