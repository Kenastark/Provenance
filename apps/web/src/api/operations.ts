/**
 * Response shapes for the operational layer (phase 7): alerts, the maintenance
 * queue, sign-off/dispatch, and admin.
 *
 * `client.ts` explains the general rule and the reason for this one exception:
 * `routers/alerts.py`, `routers/maintenance.py`, `routers/decision.py`, and
 * `routers/admin.py` all answer with `dict[str, Any]`, not a Pydantic
 * `response_model`, so `openapi-typescript` has nothing to generate a real type
 * from and `schema.d.ts` resolves every one of these responses to
 * `{ [key: string]: unknown }`. These interfaces are written by hand against the
 * router source instead (cited per type below) and will drift silently if a
 * handler's returned dict shape changes without this file changing too - unlike
 * every other response in the app, that drift is not caught by `web-contract-check`.
 * The fix, tracked as a follow-up rather than done here, is to give those four
 * routers real `response_model=` schemas and let the generator take over.
 */

// ------------------------------------------------------------- alerts (§9.5)
// src/provenance/api/routers/alerts.py, src/provenance/ops/alerts.py

/** Never a bare number: the four multiplicands behind `risk`, always shown beside it. */
export interface RiskFactors {
  genuineness: number;
  exposure: number;
  hazard: number;
  confidence_weight: number;
}

export type AlertVerdict = "GENUINE_EVENT" | "LIKELY_FAULT" | "AMBIGUOUS" | null;

export interface AlertItem {
  event_id: number;
  station_id: string;
  parameter: string;
  severity: string;
  verdict: AlertVerdict;
  confidence: number;
  exposure: number;
  headline: string;
  timestamp_utc: string;
  risk: number;
  risk_factors: RiskFactors;
}

export interface AlertsResponse {
  audit_run_id: string | null;
  ranked_by: "risk";
  note?: string;
  items: AlertItem[];
  count: number;
}

// ------------------------------------------------------- maintenance (§9.5)
// src/provenance/api/routers/maintenance.py, src/provenance/ops/maintenance.py

export type MaintenanceStatus = "open" | "acknowledged" | "dispatched" | "resolved";

export const MAINTENANCE_STATUSES: readonly MaintenanceStatus[] = [
  "open",
  "acknowledged",
  "dispatched",
  "resolved",
];

/** Forward-only lifecycle, mirroring `VALID_TRANSITIONS` in `ops/maintenance.py`. */
export const MAINTENANCE_TRANSITIONS: Record<MaintenanceStatus, readonly MaintenanceStatus[]> = {
  open: ["acknowledged"],
  acknowledged: ["dispatched", "resolved"],
  dispatched: ["resolved"],
  resolved: [],
};

export interface MaintenanceHistoryEntry {
  from_status: MaintenanceStatus | null;
  to_status: MaintenanceStatus;
  actor: string;
  note: string | null;
  at: string;
}

export interface MaintenanceEvidence {
  n_flags: number;
  severity_mix: Record<string, number>;
  importance: number;
  [key: string]: unknown;
}

export interface MaintenanceItem {
  id: number;
  audit_run_id: string;
  station_id: string;
  parameter: string;
  reason_code: string;
  severity: string;
  severity_weight: number;
  importance: number;
  priority: number;
  status: MaintenanceStatus;
  headline: string;
  n_flags: number;
  evidence: MaintenanceEvidence;
  created_at: string;
  updated_at: string;
  /** Present only on `GET /{item_id}` and `POST /{item_id}/transition`. */
  history?: MaintenanceHistoryEntry[];
}

export interface MaintenanceRebuildResult {
  audit_run_id: string;
  created: number;
}

// ---------------------------------------------------------- decision (§2, §4)
// src/provenance/api/routers/decision.py, src/provenance/api/decision/{signoff,gate}.py

export const SIGNOFF_CHANNELS = ["webhook", "email", "sms"] as const;
export type SignoffChannel = (typeof SIGNOFF_CHANNELS)[number];

export interface SignoffRecord {
  signoff_id: string;
  event_id: number;
  channel: SignoffChannel;
  operator: string;
  evidence_hash: string;
  model_version: string;
  created_at: string;
  expires_at: string;
}

export interface DispatchResult {
  dispatch_id: string;
  event_id: number;
  channel: SignoffChannel;
  signoff_id: string;
  idempotency_key: string;
  status: string;
  /** True when this call replayed a prior dispatch rather than sending a new one. */
  idempotent: boolean;
  receipt: Record<string, unknown> | null;
}

// -------------------------------------------------------------- admin (§11)
// src/provenance/api/routers/admin.py, src/provenance/ops/{store,drift}.py

export interface AdminAuditRunSummary {
  id: string;
  generated_at: string;
  n_rows: number;
  defect_rate: number;
  config_hash: string;
}

export interface AdminDispatchSummary {
  dispatch_id: string;
  event_id: number;
  channel: string;
  status: string;
  dispatched_at: string;
}

export interface AdminStatus {
  version: string;
  model_versions: Record<string, string>;
  config_hashes: { config_hash: string; trust_config_hash: string };
  retraining_triggers: Record<string, string>;
  audit_runs: AdminAuditRunSummary[];
  export_history: {
    note: string;
    n_audit_runs: number;
    dispatches: AdminDispatchSummary[];
  };
  maintenance_summary: { total: number; open: number };
}

export interface DriftPoint {
  at: string;
  value: number;
}

/** `ops/drift.py::DriftSeries.to_dict()`. `direction: "unknown"` with no points is
 * the honest "no history yet" state before `prov models train` has run. */
export interface DriftSeries {
  name: string;
  unit: string;
  points: DriftPoint[];
  baseline: number | null;
  latest: number | null;
  delta: number | null;
  direction: "up" | "down" | "flat" | "unknown";
  note: string;
}

export interface FaultConfusion {
  available: boolean;
  note?: string;
  [key: string]: unknown;
}

export interface ModelDriftReport {
  plane: "model";
  note: string;
  defect_rate_by_station: Record<string, DriftSeries>;
  deweather_r2: DriftSeries;
  conformal_coverage: DriftSeries;
  fault_confusion: FaultConfusion;
}

export interface RetrainRequestResult {
  status: "queued";
  target: string;
  command: string;
  reason: string | null;
  queued_at: string;
  note: string;
}
