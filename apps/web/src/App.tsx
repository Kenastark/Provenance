import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Outlet, Route, Routes } from "react-router-dom";
import { ApiClientProvider } from "./api/queries";
import { createClient, readApiConfig, type ApiClient } from "./api/client";
import { RoleProvider, useRole } from "./lib/role";
import { ThemeProvider } from "./lib/theme";
import { WindowProvider, useWindowState } from "./lib/windowContext";
import { TopBar } from "./features/shell/TopBar";
import { NetworkMap } from "./features/map/NetworkMap";
import { QualityMonitor } from "./features/quality/QualityMonitor";
import { EventTimeline } from "./features/timeline/EventTimeline";
import { EvidencePanel } from "./features/evidence/EvidencePanel";
import { AuditReportView } from "./features/audit/AuditReportView";
import { AlertCentre } from "./features/alerts/AlertCentre";
import { AdminDashboard } from "./features/admin/AdminDashboard";
import { RequireRole } from "./components/RequireRole";
import { EmptyState } from "./components/States";

/**
 * The application shell and its routes.
 *
 * The chrome says "Provenance". The descriptor and the demo hook live elsewhere -
 * see TopBar for why. The skip link is the first tab stop on every route, and
 * `<main>` is the target, so keyboard traversal never has to walk the nav to reach
 * the content.
 */

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // The corpus is a historical drop; refetching on every window focus would
        // spend requests re-fetching data that cannot have changed.
        refetchOnWindowFocus: false,
        staleTime: 30_000,
        retry: 1,
      },
    },
  });
}

function Shell() {
  const { timeWindow, setTimeWindow } = useWindowState();
  return (
    <div className="flex h-full min-h-0 flex-col">
      <a className="prov-skip-link" href="#main">
        Skip to content
      </a>
      <TopBar timeWindow={timeWindow} onTimeWindowChange={setTimeWindow} />
      <main id="main" className="flex min-h-0 flex-1 flex-col" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}

function NotFound() {
  return (
    <div className="p-4">
      <div className="prov-panel">
        <EmptyState
          title="No such screen"
          description="That address does not match a screen in this dashboard. Use the navigation above to reach the map, the data quality monitor, events, evidence, the audit report, the Alert Centre, or Admin."
        />
      </div>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<NetworkMap />} />
        <Route path="quality" element={<QualityMonitor />} />
        <Route path="timeline" element={<EventTimeline />} />
        <Route path="evidence" element={<EvidencePanel />} />
        <Route path="audit" element={<AuditReportView />} />
        <Route
          path="alerts"
          element={
            <RequireRole role="operator">
              <AlertCentre />
            </RequireRole>
          }
        />
        <Route
          path="admin"
          element={
            <RequireRole role="admin">
              <AdminDashboard />
            </RequireRole>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

/**
 * Builds the API client from the current role, unless a test has injected one.
 *
 * The client has to live below `RoleProvider` and be rebuilt when the role
 * changes, because the role switcher (TopBar) is how this dashboard reaches every
 * role short of a real deployment pinning `VITE_API_KEY` - see lib/role.tsx.
 */
function RoleAwareApiClientProvider({
  overrideClient,
  children,
}: {
  overrideClient?: ApiClient;
  children: ReactNode;
}) {
  const { apiKey } = useRole();
  const client = useMemo(
    () => overrideClient ?? createClient({ ...readApiConfig(), apiKey }),
    [overrideClient, apiKey],
  );
  return <ApiClientProvider value={client}>{children}</ApiClientProvider>;
}

export interface AppProps {
  queryClient?: QueryClient;
  /** Injected by tests; production resolves the client from the role. */
  apiClient?: ApiClient;
}

export function App({ queryClient, apiClient }: AppProps = {}) {
  // Built once. A client constructed inline in JSX is a *new* client on every
  // render, which empties the cache and remounts every screen under it.
  const [client] = useState(() => queryClient ?? makeQueryClient());
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <RoleProvider>
          <RoleAwareApiClientProvider overrideClient={apiClient}>
            <WindowProvider>
              <AppRoutes />
            </WindowProvider>
          </RoleAwareApiClientProvider>
        </RoleProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
