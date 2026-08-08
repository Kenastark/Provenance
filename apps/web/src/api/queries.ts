import { keepPreviousData, useQuery, type UseQueryResult } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import {
  createClient,
  type ApiClient,
  type AuditRun,
  type Defect,
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
};

// Pulling more than a page at a time is the exception, not the rule: the API caps
// a page at 500 and the dashboard's dense views want the whole small table at once.
const MAX_PAGE = 500;

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
}

export function useDefects(filters: DefectFilters = {}): UseQueryResult<Defect[]> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.defects(filters),
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }) => {
      const page = await client.get<Page<Defect>>("/v1/defects", {
        query: {
          code: filters.code,
          station: filters.station,
          severity: filters.severity,
          start: filters.start ?? undefined,
          end: filters.end ?? undefined,
          limit: filters.limit ?? MAX_PAGE,
        },
        signal,
      });
      return page.items;
    },
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
