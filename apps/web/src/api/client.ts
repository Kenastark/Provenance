import type { components, paths } from "./schema";

/**
 * A small typed fetch wrapper over the generated OpenAPI types.
 *
 * Two things it is careful about:
 *
 * 1. Every path, query shape, and response shape comes from `schema.d.ts`, which
 *    is generated from the live FastAPI schema. There are no hand-written request
 *    or response interfaces anywhere in the app, so a backend change that the
 *    client has not caught up with is a type error rather than a runtime surprise.
 * 2. The API answers errors as RFC 7807 problem documents. We parse them into
 *    `ApiError` and keep `detail` and `requestId`, because the quality floor for
 *    this dashboard says an error must state what happened - never "Something
 *    went wrong". `detail` is the sentence the backend wrote; `requestId` is what
 *    an operator quotes when they ask someone to look at the log.
 */

const DEFAULT_BASE_URL = "http://localhost:8000";

// Documented local-dev key (see src/provenance/api/auth.py). The dashboard is the
// operator surface, so it asks for the operator role. Any real deployment sets
// VITE_API_KEY and PROVENANCE_API_KEYS to something that is not in the repository.
const DEFAULT_API_KEY = "prov-operator-key";

export interface ApiConfig {
  baseUrl: string;
  apiKey: string;
}

export function readApiConfig(env: Record<string, string | undefined> = import.meta.env): ApiConfig {
  return {
    baseUrl: (env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, ""),
    apiKey: env.VITE_API_KEY ?? DEFAULT_API_KEY,
  };
}

/** An RFC 7807 problem document, plus the transport failures that produce no body. */
export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail: string;
  readonly requestId: string | null;
  /** True when the request never reached the API at all (offline, DNS, CORS). */
  readonly isNetworkError: boolean;

  constructor(init: {
    status: number;
    title: string;
    detail: string;
    requestId?: string | null;
    isNetworkError?: boolean;
  }) {
    super(init.detail || init.title);
    this.name = "ApiError";
    this.status = init.status;
    this.title = init.title;
    this.detail = init.detail;
    this.requestId = init.requestId ?? null;
    this.isNetworkError = init.isNetworkError ?? false;
  }

  /**
   * What an operator should do about it. Paired with `detail` (what happened) this
   * is the whole of the app's error contract.
   */
  get remedy(): string {
    if (this.isNetworkError) {
      return "The API did not respond. Check that the stack is running (`make up`) and reload.";
    }
    switch (this.status) {
      case 401:
      case 403:
        return "This dashboard's API key does not grant access to that data. Check VITE_API_KEY.";
      case 404:
        return "Load a data drop first (`make demo`), then retry.";
      case 422:
      case 400:
        return "Adjust the filter or time window and try again.";
      default:
        return this.requestId
          ? `Retry, and quote request id ${this.requestId} if it keeps failing.`
          : "Retry. If it keeps failing, check the API logs.";
    }
  }
}

type ProblemBody = {
  title?: unknown;
  detail?: unknown;
  status?: unknown;
  request_id?: unknown;
};

async function toApiError(response: Response): Promise<ApiError> {
  let body: ProblemBody = {};
  try {
    body = (await response.json()) as ProblemBody;
  } catch {
    // A proxy or gateway can fail before FastAPI sees the request, in which case
    // there is no problem document to read. Fall through to the status text.
  }
  return new ApiError({
    status: response.status,
    title: typeof body.title === "string" ? body.title : response.statusText || "Request failed",
    detail:
      typeof body.detail === "string"
        ? body.detail
        : `The API returned ${response.status} for this request.`,
    requestId:
      typeof body.request_id === "string" && body.request_id
        ? body.request_id
        : response.headers.get("X-Request-ID"),
  });
}

/** Query values the API accepts. `undefined` and `null` are dropped, not sent empty. */
export type QueryValue = string | number | boolean | undefined | null;

export function buildUrl(
  baseUrl: string,
  path: string,
  query?: Record<string, QueryValue>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return `${baseUrl}${path}${qs ? `?${qs}` : ""}`;
}

export interface RequestOptions {
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
}

export function createClient(config: ApiConfig = readApiConfig(), fetchImpl: typeof fetch = fetch) {
  async function get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = buildUrl(config.baseUrl, path, options.query);
    let response: Response;
    try {
      response = await fetchImpl(url, {
        method: "GET",
        headers: { Accept: "application/json", "X-API-Key": config.apiKey },
        signal: options.signal,
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
      throw new ApiError({
        status: 0,
        title: "No response from the API",
        detail: `The request to ${url} could not be completed.`,
        isNetworkError: true,
      });
    }
    if (!response.ok) throw await toApiError(response);
    return (await response.json()) as T;
  }

  return { config, get };
}

export type ApiClient = ReturnType<typeof createClient>;

// ---------------------------------------------------------------- shorthands
// Named aliases for the response shapes the UI consumes, every one of them
// resolved out of the generated schema rather than restated by hand.
type Schemas = components["schemas"];

export type Station = Schemas["StationOut"];
export type Reading = Schemas["ReadingOut"];
export type Defect = Schemas["DefectOut"];
export type ProvEvent = Schemas["EventOut"];
export type AuditRun = Schemas["AuditRunOut"];
export type QualitySummary = Schemas["QualitySummaryOut"];
export type QualityStation = Schemas["QualityStationOut"];
export type TrustScore = Schemas["TrustScoreOut"];
export type TrustComponent = Schemas["ComponentOut"];
export type Version = Schemas["VersionOut"];
export type Explain = Schemas["ExplainOut"];
export type Attribution = Schemas["AttributionOut"];
export type DeweatherSeries = Schemas["DeweatherSeriesOut"];
export type DeweatherPoint = Schemas["DeweatherPointOut"];
export type BusStop = Schemas["BusStopOut"];
export type ReferenceStops = Schemas["ReferenceStopsOut"];
export type TrafficCounter = Schemas["TrafficCounterOut"];
export type ReferenceCounters = Schemas["ReferenceCountersOut"];

/** Every list endpoint answers with this envelope. */
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  count: number;
}

/**
 * Compile-time proof that the aliases above still line up with the routes.
 *
 * If the backend renames a schema or changes a route's response, this fails to
 * typecheck - which is the point. It costs nothing at runtime.
 */
type AssertAssignable<A extends B, B> = A;
export type _StationRouteMatches = AssertAssignable<
  NonNullable<paths["/v1/stations"]["get"]["responses"][200]["content"]>["application/json"]["items"][number],
  Station
>;
export type _QualityRouteMatches = AssertAssignable<
  NonNullable<
    paths["/v1/quality/summary"]["get"]["responses"][200]["content"]
  >["application/json"],
  QualitySummary
>;
export type _ReferenceStopsRouteMatches = AssertAssignable<
  NonNullable<paths["/v1/reference/bus-stops"]["get"]["responses"][200]["content"]>["application/json"],
  ReferenceStops
>;
export type _ReferenceCountersRouteMatches = AssertAssignable<
  NonNullable<
    paths["/v1/reference/traffic-counters"]["get"]["responses"][200]["content"]
  >["application/json"],
  ReferenceCounters
>;
