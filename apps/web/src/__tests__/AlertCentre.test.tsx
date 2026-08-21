import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { AlertCentre } from "../features/alerts/AlertCentre";
import { resetSignoffCache } from "../lib/signoffs";
import * as fixtures from "../test/fixtures";
import { renderWithProviders } from "../test/harness";

function renderScreen(overrides: Parameters<typeof renderWithProviders>[1] = {}) {
  return renderWithProviders(<AlertCentre />, { route: "/alerts", ...overrides });
}

/** The two DataTables on this screen (the alert list and the maintenance queue)
 * both emit `data-table-row`, so every test scopes its row queries to one named
 * region rather than trusting DOM order between the two tables. */
async function findAlertRows() {
  const region = await screen.findByRole("region", { name: /^alert centre$/i });
  return within(region).findAllByTestId("data-table-row");
}

const signoffRoute = (body: unknown) => {
  const input = body as { event_id: number; channel: string; operator: string };
  // Real, not fixed, timestamps: `isSignoffUsable` checks `expires_at` against the
  // real clock, and this suite has to keep passing after the fixed date below it.
  return {
    signoff_id: "so_test1",
    event_id: input.event_id,
    channel: input.channel,
    operator: input.operator,
    evidence_hash: "hash0123456789",
    model_version: "trust_score=v1",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
  };
};

const dispatchRoute = (body: unknown) => {
  const input = body as { event_id: number; channel: string; signoff_id: string };
  return {
    dispatch_id: "dsp_test1",
    event_id: input.event_id,
    channel: input.channel,
    signoff_id: input.signoff_id,
    idempotency_key: `${input.event_id}:${input.channel}:${input.signoff_id}`,
    status: "sent",
    idempotent: false,
    receipt: null,
  };
};

describe("AlertCentre", () => {
  beforeEach(() => {
    resetSignoffCache();
  });

  it("ranks a lower-confidence, high-exposure event above a confident, low-exposure fault", async () => {
    renderScreen();

    const rows = await findAlertRows();
    // Fixture risk: STA-03 (AMBIGUOUS, confidence 0.55, exposure 0.95) = 0.352,
    // STA-02 (LIKELY_FAULT, confidence 0.97, exposure 0.20) = 0.146. The lower-
    // confidence, higher-exposure event must rank first - that inversion is the
    // whole product argument, not an incidental sort.
    expect(within(rows[0]!).getByRole("rowheader")).toHaveTextContent("STA-03");
    expect(within(rows[1]!).getByRole("rowheader")).toHaveTextContent("STA-02");
  });

  it("shows severity and exposure beside risk, so the inversion is legible in the list", async () => {
    renderScreen();
    await findAlertRows();

    const list = screen.getByRole("region", { name: /^alert centre$/i });
    for (const header of ["Severity", "Exposure", "Confidence", "Risk"]) {
      expect(within(list).getByRole("columnheader", { name: new RegExp(header, "i") })).toBeInTheDocument();
    }
  });

  it("opens an alert's detail with its risk factors, never a bare risk number", async () => {
    const user = userEvent.setup();
    renderScreen();

    const rows = await findAlertRows();
    await user.click(rows[0]!);

    const detail = await screen.findByTestId("alert-detail");
    const breakdown = within(detail).getByTestId("factor-breakdown");
    expect(within(breakdown).getByText("Genuineness")).toBeInTheDocument();
    expect(within(breakdown).getByText("Exposure (rel.)")).toBeInTheDocument();
    expect(within(breakdown).getByText("Hazard")).toBeInTheDocument();
    expect(within(breakdown).getByText("Confidence weight")).toBeInTheDocument();
  });

  it("reuses the trust chip and breakdown components for the station's trust score", async () => {
    const user = userEvent.setup();
    renderScreen();

    const rows = await findAlertRows();
    await user.click(rows[0]!);

    const detail = await screen.findByTestId("alert-detail");
    expect(await within(detail).findByTestId("trust-chip")).toBeInTheDocument();
    expect(within(detail).getByTestId("trust-breakdown")).toBeInTheDocument();
  });

  it("blocks dispatch in words an operator could read aloud until a sign-off exists", async () => {
    const user = userEvent.setup();
    renderScreen({ postRoutes: { "/v1/decision/signoff": signoffRoute, "/v1/decision/dispatch": dispatchRoute } });

    const rows = await findAlertRows();
    await user.click(rows[0]!);

    const dispatchButton = await screen.findByTestId("dispatch-button");
    expect(dispatchButton).toBeDisabled();
    expect(screen.getByTestId("dispatch-blocked")).toHaveTextContent(/no valid, unexpired sign-off/i);
  });

  it("unblocks and completes dispatch once a sign-off is recorded", async () => {
    const user = userEvent.setup();
    renderScreen({ postRoutes: { "/v1/decision/signoff": signoffRoute, "/v1/decision/dispatch": dispatchRoute } });

    const rows = await findAlertRows();
    await user.click(rows[0]!);
    await screen.findByTestId("signoff-panel");

    await user.click(screen.getByRole("button", { name: /record sign-off/i }));

    await waitFor(() => expect(screen.getByTestId("dispatch-button")).not.toBeDisabled());
    expect(screen.getByTestId("signoff-records")).toHaveTextContent(/valid/);

    await user.click(screen.getByTestId("dispatch-button"));

    const success = await screen.findByTestId("dispatch-success");
    expect(success).toHaveTextContent(/Status sent/);
  });

  it("shows the maintenance queue with its lifecycle states", async () => {
    renderScreen();

    const queue = await screen.findByRole("region", { name: /maintenance queue/i });
    expect(await within(queue).findByText(/STA-03/)).toBeInTheDocument();
    const table = within(queue).getByTestId("data-table");
    expect(within(table).getByText("Open")).toBeInTheDocument();
    expect(within(table).getByText("Acknowledged")).toBeInTheDocument();
  });

  it("only offers the maintenance ticket's next lifecycle status, forward-only", async () => {
    const user = userEvent.setup();
    renderScreen();

    const queue = await screen.findByRole("region", { name: /maintenance queue/i });
    const rows = await within(queue).findAllByTestId("data-table-row");
    // Row 0 sorts by priority desc: STA-03 (open, priority 0.95) first.
    await user.click(rows[0]!);

    const detail = await screen.findByTestId("maintenance-ticket-detail");
    expect(within(detail).getByTestId("transition-acknowledged")).toBeInTheDocument();
    expect(within(detail).queryByTestId("transition-dispatched")).not.toBeInTheDocument();
    expect(within(detail).queryByTestId("transition-resolved")).not.toBeInTheDocument();
  });

  it("shows an empty queue honestly rather than hiding the section", async () => {
    renderScreen({ routes: { "/v1/maintenance": { items: [], next_cursor: null, count: 0 } } });

    const queue = await screen.findByRole("region", { name: /maintenance queue/i });
    expect(await within(queue).findByText(/queue is empty/i)).toBeInTheDocument();
  });

  it("shows an honest empty state when there are no alerts, not a blank screen", async () => {
    renderScreen({ routes: { "/v1/alerts": fixtures.alertsResponse({ items: [], count: 0 }) } });

    expect(await screen.findByText(/no candidate alerts/i)).toBeInTheDocument();
  });
});
