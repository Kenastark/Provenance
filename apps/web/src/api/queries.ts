import { keepPreviousData, useQuery, type UseQueryResult } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import {
  createClient,
  type ApiClient,
  type AuditRun,
  type Defect,
  type DeweatherSeries,
  type Explain,
  type Page,
  type ProvEvent,
  type QualitySummary,
  type Reading,
  type Station,
  type TrustScore,
  type Version,
} from "./client";

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
  quality: (runId?: string) => ["quality", runId ?? "latest"] as const,
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

export function useQualitySummary(runId?: string): UseQueryResult<QualitySummary> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.quality(runId),
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      client.get<QualitySummary>("/v1/quality/summary", { query: { run_id: runId }, signal }),
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
