import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { createContext, useContext } from "react";
import {
  createClient,
  type ApiClient,
  type AttentionOverlay,
  type AuditRun,
  type Defect,
  type DeweatherSeries,
  type Explain,
  type Page,
  type ProvEvent,
  type QualitySummary,
  type Reading,
  type ReferenceCounters,
  type ReferenceStops,
  type Station,
  type TrustScore,
  type Version,
} from "./client";
import type {
  AdminStatus,
  AlertsResponse,
  DispatchResult,
  MaintenanceItem,
  MaintenanceRebuildResult,
  MaintenanceStatus,
  ModelDriftReport,
  RetrainRequestResult,
  SignoffChannel,
  SignoffRecord,
} from "./operations";

/**
 * Data access for the dashboard.
 *
 * Every hook here is read-only, because in phase 3 the whole product is read-only:
 * the only write surface is the local action queue, which deliberately has no
 * transport (see lib/queue.ts).
 *
 * The client is injected through context so tests can hand in a stub and exercise
 * the real hooks. Nothing constructs a client at module scope.
 */

const ApiClientContext = createContext<ApiClient | null>(null);
export const ApiClientProvider = ApiClientContext.Provider;

export function useApiClient(): ApiClient {
  return useContext(ApiClientContext) ?? defaultClient();
}

let fallback: ApiClient | null = null;
function defaultClient(): ApiClient {
  fallback ??= createClient();
  return fallback;
}

export const queryKeys = {
  version: ["version"] as const,
  stations: ["stations"] as const,
  quality: (runId?: string, start?: string | null, end?: string | null) =>
    ["quality", runId ?? "latest", start ?? null, end ?? null] as const,
  auditRuns: ["audit", "runs"] as const,
  auditRun: (runId: string) => ["audit", "run", runId] as const,
  events: (stationId?: string) => ["events", stationId ?? "all"] as const,
  defects: (filters: DefectFilters) => ["defects", filters] as const,
  trust: (stationId: string) => ["trust", stationId] as const,
  trustSeries: (stationId: string) => ["trust", stationId, "series"] as const,
  readings: (stationId: string, parameter: string | undefined, start?: string | null) =>
    ["readings", stationId, parameter ?? "all", start ?? "any"] as const,
  explain: (defectId: number | string) => ["explain", String(defectId)] as const,
  deweather: (stationId: string, parameter: string) =>
    ["deweather", stationId, parameter] as const,
  busStops: ["reference", "bus-stops"] as const,
  trafficCounters: ["reference", "traffic-counters"] as const,
  attentionOverlay: ["graph", "attention"] as const,
  alerts: (runId?: string) => ["alerts", runId ?? "latest"] as const,
  maintenance: (status?: string) => ["maintenance", status ?? "all"] as const,
  maintenanceItem: (id: number) => ["maintenance", "item", id] as const,
  adminStatus: ["admin", "status"] as const,
  modelDrift: ["admin", "model-drift"] as const,
};

// Pulling more than a page at a time is the exception, not the rule: the API caps
// a page at 500 and the dashboard's dense views want the whole small table at once.
const MAX_PAGE = 500;

// A traversal cap, not a page size. 100 pages is 50,000 rows - more than the real
// corpus produces - and it exists only so a paging bug cannot spin forever.
const MAX_PAGES = 100;

export function useVersion(): UseQueryResult<Version> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.version,
    queryFn: ({ signal }) => client.get<Version>("/version", { signal }),
    staleTime: Infinity,
  });
}

export function useStations(): UseQueryResult<Station[]> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.stations,
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<Station>>("/v1/stations", {
        query: { limit: MAX_PAGE },
        signal,
      });
      return page.items;
    },
  });
}

/** Reference layers (bus stops, traffic counters): real coordinates only, or
 * ``available: false`` when the source drop was never loaded (never a silent
 * empty layer - see stationMarkers.ts's LayerDefinition). */
export function useBusStops(): UseQueryResult<ReferenceStops> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.busStops,
    queryFn: ({ signal }) => client.get<ReferenceStops>("/v1/reference/bus-stops", { signal }),
    staleTime: Infinity,
  });
}

export function useTrafficCounters(): UseQueryResult<ReferenceCounters> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.trafficCounters,
    queryFn: ({ signal }) =>
      client.get<ReferenceCounters>("/v1/reference/traffic-counters", { signal }),
    staleTime: Infinity,
  });
}

/** The HST-GAT's attention overlay: real edges, or `available: false` with the
 * backend's own reason (e.g. "has not been trained") - see stationMarkers.ts's
 * LayerDefinition and the attentionOverlay entry in MAP_LAYERS. */
export function useAttentionOverlay(): UseQueryResult<AttentionOverlay> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.attentionOverlay,
    queryFn: ({ signal }) => client.get<AttentionOverlay>("/v1/graph/attention", { signal }),
    staleTime: Infinity,
  });
}

/** ``window`` bounds the served ``uptime_pct``/``last_calibration_at`` figures to
 * the operator's selected time window, the same way `useDefects`' start/end do;
 * omit it for an unbounded call (e.g. the window anchor itself, which cannot
 * depend on a window it has not resolved yet). */
export function useQualitySummary(
  runId?: string,
  window?: { start?: string | null; end?: string | null },
): UseQueryResult<QualitySummary> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.quality(runId, window?.start, window?.end),
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      client.get<QualitySummary>("/v1/quality/summary", {
        query: { run_id: runId, start: window?.start ?? undefined, end: window?.end ?? undefined },
        signal,
      }),
  });
}

export function useAuditRuns(): UseQueryResult<AuditRun[]> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.auditRuns,
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<AuditRun>>("/v1/audit/runs", {
        query: { limit: MAX_PAGE },
        signal,
      });
      return page.items;
    },
  });
}

/** The full stored summary for one run - what the Audit Report view renders. */
export interface AuditRunDetail {
  run: AuditRun;
  summary: Record<string, unknown>;
}

export function useAuditRun(runId: string | undefined): UseQueryResult<AuditRunDetail> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.auditRun(runId ?? ""),
    enabled: Boolean(runId),
    queryFn: ({ signal }) => client.get<AuditRunDetail>(`/v1/audit/runs/${runId}`, { signal }),
  });
}

export function useEvents(stationId?: string): UseQueryResult<ProvEvent[]> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.events(stationId),
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<ProvEvent>>("/v1/events", {
        query: { station: stationId, limit: MAX_PAGE },
        signal,
      });
      return page.items;
    },
  });
}

export interface DefectFilters {
  code?: string;
  station?: string;
  severity?: string;
  start?: string | null;
  end?: string | null;
  limit?: number;
  enabled?: boolean;
}

/** A fully-traversed list, plus whether the traversal was cut short by the cap. */
export interface Paginated<T> {
  items: T[];
  /** True when the cap stopped the walk while more rows remained upstream. */
  truncated: boolean;
}

/**
 * Follow a cursor to exhaustion, so a count is a count.
 *
 * The list endpoints page at 500. Anything that *counts* the rows it fetched -
 * the quality monitor's absent-cell numerator, a filtered defect total - is
 * silently wrong the moment a query exceeds one page. `maxPages` stops a runaway
 * traversal; when it bites, `truncated` says so, so a consumer can tell the user
 * it is looking at a prefix rather than the whole set. The alternative - inferring
 * truncation from `items.length === maxPages * pageSize` - is the kind of implicit
 * signal that stops being true the moment a page comes back short.
 */
export async function paginateAll<T>(
  client: ApiClient,
  path: string,
  query: Record<string, string | number | boolean | undefined>,
  signal: AbortSignal | undefined,
  maxPages = MAX_PAGES,
): Promise<Paginated<T>> {
  const items: T[] = [];
  let cursor: string | null = null;
  for (let fetched = 0; fetched < maxPages; fetched += 1) {
    const page: Page<T> = await client.get<Page<T>>(path, {
      query: { ...query, cursor: cursor ?? undefined },
      signal,
    });
    items.push(...page.items);
    if (!page.next_cursor) return { items, truncated: false };
    cursor = page.next_cursor;
  }
  // Left the loop with a cursor still in hand: there is more upstream than the cap
  // let us fetch.
  return { items, truncated: true };
}

export function useDefects(filters: DefectFilters = {}): UseQueryResult<Paginated<Defect>> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.defects(filters),
    placeholderData: keepPreviousData,
    enabled: filters.enabled ?? true,
    queryFn: ({ signal }) =>
      paginateAll<Defect>(
        client,
        "/v1/defects",
        {
          code: filters.code,
          station: filters.station,
          severity: filters.severity,
          start: filters.start ?? undefined,
          end: filters.end ?? undefined,
          limit: filters.limit ?? MAX_PAGE,
        },
        signal,
      ),
  });
}

export function useTrust(stationId: string | undefined): UseQueryResult<TrustScore> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.trust(stationId ?? ""),
    enabled: Boolean(stationId),
    queryFn: ({ signal }) => client.get<TrustScore>(`/v1/trust/${stationId}`, { signal }),
  });
}

/** The score history, oldest first, so a sparkline reads left to right. */
export function useTrustSeries(stationId: string | undefined): UseQueryResult<TrustScore[]> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.trustSeries(stationId ?? ""),
    enabled: Boolean(stationId),
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<TrustScore>>(`/v1/trust/${stationId}`, {
        query: { series: true, limit: MAX_PAGE },
        signal,
      });
      return [...page.items].sort((a, b) => a.timestamp_utc.localeCompare(b.timestamp_utc));
    },
  });
}

/**
 * The SHAP explanation for one flagged reading (phase 5).
 *
 * Returns the model-backed attributions and operator sentence when the model
 * artefacts are present, and a `degraded` explanation (statistics-layer reason, no
 * attributions) when they are not - so the evidence panel always has something honest
 * to show, never a spinner that never resolves.
 */
export function useExplain(defectId: number | undefined): UseQueryResult<Explain> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.explain(defectId ?? ""),
    enabled: Boolean(defectId),
    queryFn: ({ signal }) => client.get<Explain>(`/v1/explain/${defectId}`, { signal }),
  });
}

/** The deweathered before/after series for a station's pollutant (raw vs residual). */
export function useDeweather(
  stationId: string | undefined,
  parameter: string | undefined,
): UseQueryResult<DeweatherSeries> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.deweather(stationId ?? "", parameter ?? ""),
    enabled: Boolean(stationId) && Boolean(parameter),
    queryFn: ({ signal }) =>
      client.get<DeweatherSeries>(`/v1/deweather/${stationId}`, {
        query: { parameter },
        signal,
      }),
  });
}

// ------------------------------------------------------ operational layer
// The rest of this module is phase 7: the Alert Centre, the maintenance queue,
// the sign-off/dispatch gate, and admin. Unlike every hook above, several of these
// are writes - this is the first part of the dashboard where a click has a real,
// remote consequence, so every mutation below awaits its real result rather than
// applying an optimistic update.

// The alerts endpoint has no cursor - it is a ranked top-N, not a full listing -
// and 200 is its own hard maximum (`Query(..., le=200)` in routers/alerts.py).
const ALERTS_LIMIT = 200;

export function useAlerts(runId?: string): UseQueryResult<AlertsResponse> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.alerts(runId),
    queryFn: ({ signal }) =>
      client.get<AlertsResponse>("/v1/alerts", {
        query: { run_id: runId, limit: ALERTS_LIMIT },
        signal,
      }),
  });
}

/** The maintenance queue, fully traversed (see `paginateAll`) so a queue length is
 * a real count and not a first page. */
export function useMaintenanceQueue(status?: MaintenanceStatus): UseQueryResult<Paginated<MaintenanceItem>> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.maintenance(status),
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      paginateAll<MaintenanceItem>(client, "/v1/maintenance", { status, limit: MAX_PAGE }, signal),
  });
}

/** One item with its full transition history, for the queue's detail pane. */
export function useMaintenanceItem(id: number | undefined): UseQueryResult<MaintenanceItem> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.maintenanceItem(id ?? -1),
    enabled: id !== undefined,
    queryFn: ({ signal }) => client.get<MaintenanceItem>(`/v1/maintenance/${id}`, { signal }),
  });
}

export function useAdminStatus(): UseQueryResult<AdminStatus> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.adminStatus,
    queryFn: ({ signal }) => client.get<AdminStatus>("/v1/admin/status", { signal }),
  });
}

/** The model plane of the two-plane monitor - see AdminDashboard for the infra plane. */
export function useModelDrift(): UseQueryResult<ModelDriftReport> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.modelDrift,
    queryFn: ({ signal }) => client.get<ModelDriftReport>("/v1/admin/model-drift", { signal }),
  });
}

export interface CreateSignoffInput {
  event_id: number;
  channel: SignoffChannel;
  operator: string;
  evidence?: Record<string, unknown>;
  ttl_seconds?: number;
}

/** Records who saw what and signed off on it. Does not send anything - see
 * useDispatchAlert, and the standing rule that separates the two (§2, rule 5). */
export function useCreateSignoff(): UseMutationResult<SignoffRecord, unknown, CreateSignoffInput> {
  const client = useApiClient();
  return useMutation({
    mutationFn: (input) => client.post<SignoffRecord>("/v1/decision/signoff", input),
  });
}

export interface DispatchInput {
  event_id: number;
  channel: SignoffChannel;
  signoff_id: string;
}

/** The one and only path to a public dispatch. The backend refuses this (422,
 * `.../problems/signoff-required`) without a valid, unexpired sign-off for this
 * exact event and channel - see `gate.dispatch` and `test_signoff_gate.py`. This
 * hook does not, and must not, offer any other way to reach it. */
export function useDispatchAlert(): UseMutationResult<DispatchResult, unknown, DispatchInput> {
  const client = useApiClient();
  return useMutation({
    mutationFn: (input) => client.post<DispatchResult>("/v1/decision/dispatch", input),
  });
}

export interface TransitionInput {
  id: number;
  to: MaintenanceStatus;
  actor: string;
  note?: string;
}

export function useMaintenanceTransition(): UseMutationResult<MaintenanceItem, unknown, TransitionInput> {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) => client.post<MaintenanceItem>(`/v1/maintenance/${id}/transition`, body),
    onSuccess: (item) => {
      queryClient.setQueryData(queryKeys.maintenanceItem(item.id), item);
      void queryClient.invalidateQueries({ queryKey: ["maintenance"] });
    },
  });
}

/** Raises tickets for any (station, parameter, reason code) the latest run flagged
 * that the queue does not already carry. Idempotent - see `rebuild_maintenance`. */
export function useRebuildMaintenance(): UseMutationResult<MaintenanceRebuildResult, unknown, void> {
  const client = useApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.post<MaintenanceRebuildResult>("/v1/maintenance/rebuild", {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["maintenance"] });
    },
  });
}

export interface RetrainInput {
  target: string;
  reason?: string;
}

/** Records a retraining *request*; see admin.py's own docstring - it never trains
 * inline, and this dashboard must not imply otherwise. */
export function useRequestRetrain(): UseMutationResult<RetrainRequestResult, unknown, RetrainInput> {
  const client = useApiClient();
  return useMutation({
    mutationFn: (input) => client.post<RetrainRequestResult>("/v1/admin/retrain", input),
  });
}

export function useReadings(options: {
  stationId: string | undefined;
  parameter?: string;
  start?: string | null;
  end?: string | null;
  limit?: number;
  enabled?: boolean;
}): UseQueryResult<Reading[]> {
  const client = useApiClient();
  const { stationId, parameter, start, end, limit, enabled = true } = options;
  return useQuery({
    queryKey: queryKeys.readings(stationId ?? "", parameter, start),
    placeholderData: keepPreviousData,
    enabled: enabled && Boolean(stationId),
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<Reading>>("/v1/readings", {
        query: {
          station: stationId,
          parameter,
          start: start ?? undefined,
          end: end ?? undefined,
          quality_flagged: true,
          limit: limit ?? MAX_PAGE,
        },
        signal,
      });
      return [...page.items].sort((a, b) => a.timestamp_utc.localeCompare(b.timestamp_utc));
    },
  });
}
