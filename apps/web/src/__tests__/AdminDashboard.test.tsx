import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminDashboard } from "../features/admin/AdminDashboard";
import { renderWithProviders } from "../test/harness";

function renderScreen(overrides: Parameters<typeof renderWithProviders>[1] = {}) {
  return renderWithProviders(<AdminDashboard />, { route: "/admin", ...overrides });
}

/** `useInfraMetrics` deliberately bypasses the injected ApiClient - `/metrics` is
 * unauthenticated and outside its JSON contract - so it has to be stubbed at the
 * global `fetch` level rather than through `stubClient`'s routes. */
function stubMetrics(text = "prov_up 1\nprov_http_requests_total{method=\"GET\"} 10\nprov_http_requests_in_flight 0\n") {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(text, { status: 200, headers: { "Content-Type": "text/plain" } })),
  );
}

describe("AdminDashboard", () => {
  beforeEach(() => {
    stubMetrics();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the role hierarchy, admin granting everything beneath it", async () => {
    renderScreen();
    const matrix = await screen.findByTestId("rbac-matrix");
    const rows = within(matrix).getAllByTestId("rbac-role-row");
    const adminRow = rows.find((row) => within(row).queryByText(/^admin/i));
    expect(adminRow).toBeDefined();
    expect(adminRow).toHaveTextContent(/Public read \+ Researcher \+ Operator \+ Admin/);
  });

  it("marks an admin-only endpoint blocked for a role that does not reach it", async () => {
    renderScreen({ envApiKey: "prov-operator-key" });
    const matrix = await screen.findByTestId("rbac-matrix");
    const row = within(matrix)
      .getAllByTestId("rbac-endpoint-row")
      .find((candidate) => within(candidate).queryByText(/admin\/model-drift/));
    expect(row).toHaveTextContent(/blocked/i);
  });

  it("marks the same endpoint reachable for admin", async () => {
    renderScreen({ envApiKey: "prov-admin-key" });
    const matrix = await screen.findByTestId("rbac-matrix");
    const row = within(matrix)
      .getAllByTestId("rbac-endpoint-row")
      .find((candidate) => within(candidate).queryByText(/admin\/model-drift/));
    expect(row).toHaveTextContent(/reachable/i);
  });

  it("shows version, config hashes, and the audit run history", async () => {
    renderScreen();
    expect(await screen.findByText("0.3.0")).toBeInTheDocument();
    expect(screen.getAllByText("cfg0123456").length).toBeGreaterThan(0);
    expect(screen.getByText("run-2026-05-15")).toBeInTheDocument();
  });

  it("records a retrain request and shows the honest 'does not train inline' note", async () => {
    const user = userEvent.setup();
    renderScreen({
      postRoutes: {
        "/v1/admin/retrain": (body: unknown) => ({
          status: "queued",
          target: (body as { target: string }).target,
          command: "prov models train",
          reason: null,
          queued_at: new Date().toISOString(),
          note: "Retraining runs as a CLI/worker job; this records the request, it does not train inline.",
        }),
      },
    });

    await user.click(await screen.findByTestId("retrain-deweather"));

    expect(await screen.findByText(/does not train inline/i)).toBeInTheDocument();
  });

  it("says 'no history yet' rather than drawing a one-point chart", async () => {
    renderScreen();
    const noHistory = await screen.findByTestId("drift-no-history");
    expect(noHistory).toHaveTextContent(/no history yet/i);
    // Conformal coverage is the no-history fixture; it must not also render a chart.
    // Matched against the panel's own <h4>, not textContent generally - a rendered
    // Sparkline's accessible summary also starts with the series name, which would
    // otherwise double-match inside the same panel.
    const panels = screen.getAllByTestId("drift-series-panel");
    const conformalPanel = panels.find((panel) => /conformal coverage/i.test(panel.querySelector("h4")?.textContent ?? ""));
    expect(conformalPanel && within(conformalPanel).queryByTestId("sparkline")).toBeNull();
  });

  it("draws a chart for a series that does have history", async () => {
    renderScreen();
    const panels = await screen.findAllByTestId("drift-series-panel");
    const r2Panel = panels.find((panel) => /deweather r/i.test(panel.querySelector("h4")?.textContent ?? ""));
    expect(r2Panel && within(r2Panel).getByTestId("sparkline")).toBeInTheDocument();
  });

  it("shows the fault confusion panel as not yet computed rather than a fabricated matrix", async () => {
    renderScreen();
    const notYetComputed = await screen.findByTestId("not-yet-computed");
    expect(notYetComputed).toHaveTextContent(/train the fault classifier/i);
  });

  it("reads the infra plane from /metrics", async () => {
    renderScreen();
    const infra = await screen.findByTestId("infra-health-panel");
    expect(await within(infra).findByText("up")).toBeInTheDocument();
    expect(within(infra).getByText("10")).toBeInTheDocument();
  });
});
