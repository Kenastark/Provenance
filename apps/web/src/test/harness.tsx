import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement, ReactNode } from "react";
import { ApiClientProvider } from "../api/queries";
import type { ApiClient, Page } from "../api/client";
import { ApiError } from "../api/client";
import { ThemeProvider } from "../lib/theme";
import { WindowProvider } from "../lib/windowContext";
import * as fixtures from "./fixtures";

/**
 * Rendering a screen with the real hooks and a stub transport.
 *
 * The stub replaces `client.get`, not the hooks, so every test exercises the actual
 * TanStack Query wiring, the actual URL building, and the actual response mapping.
 * A test that passes here has proved the component works against the shape the
 * generated OpenAPI types describe.
 */

export function page<T>(items: T[]): Page<T> {
  return { items, next_cursor: null, count: items.length };
}

export type RouteMap = Record<string, unknown>;

export const defaultRoutes: RouteMap = {
  "/version": fixtures.version,
  "/v1/stations": page(fixtures.stations),
  "/v1/quality/summary": fixtures.qualitySummary,
  "/v1/audit/runs": page([fixtures.auditRun()]),
  "/v1/events": page(fixtures.events),
  "/v1/defects": page(fixtures.defects),
  "/v1/readings": page(fixtures.readings),
  "/v1/trust/STA-01": fixtures.trustScore(),
  "/v1/trust/STA-02": fixtures.trustScore({ station_id: "STA-02", trust: 0.93, reason_codes: ["T00"] }),
  "/v1/trust/STA-03": fixtures.trustScore({ station_id: "STA-03", trust: 0.22, reason_codes: ["T04"] }),
};

export interface StubOptions {
  routes?: RouteMap;
  /** Paths that should reject, mapped to the error to throw. */
  failures?: Record<string, ApiError>;
  onRequest?: (path: string, query: Record<string, unknown> | undefined) => void;
}

export function stubClient(options: StubOptions = {}): ApiClient {
  const routes = { ...defaultRoutes, ...(options.routes ?? {}) };
  return {
    config: { baseUrl: "http://api.test", apiKey: "test-key" },
    async get<T>(path: string, requestOptions: { query?: Record<string, unknown> } = {}) {
      options.onRequest?.(path, requestOptions.query);
      const failure = options.failures?.[path];
      if (failure) throw failure;
      if (!(path in routes)) {
        throw new ApiError({
          status: 404,
          title: "Not Found",
          detail: `The stub has no fixture for ${path}.`,
        });
      }
      return routes[path] as T;
    },
  } as ApiClient;
}

export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
    // Errors are the subject of several tests; the console noise is not useful.
    logger: undefined,
  } as never);
}

export interface HarnessOptions extends StubOptions {
  route?: string;
  client?: ApiClient;
}

export function Providers({
  children,
  route = "/",
  client,
  ...stub
}: HarnessOptions & { children: ReactNode }) {
  // Same reason as App: one client per mount, not one per render.
  const [queryClient] = useState(makeTestQueryClient);
  const [apiClient] = useState(() => client ?? stubClient(stub));
  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider value={apiClient}>
        <ThemeProvider>
          <MemoryRouter initialEntries={[route]}>
            <WindowProvider>{children}</WindowProvider>
          </MemoryRouter>
        </ThemeProvider>
      </ApiClientProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options: HarnessOptions = {},
): RenderResult {
  return render(<Providers {...options}>{ui}</Providers>);
}
