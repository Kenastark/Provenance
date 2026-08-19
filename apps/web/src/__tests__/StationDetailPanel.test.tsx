import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { StationDetailPanel } from "../features/station/StationDetailPanel";
import { clearQueue, listQueuedActions, resetQueueCache } from "../lib/queue";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

const station = fixtures.station();
const qualityRow = fixtures.qualityStation();

function renderPanel(overrides: Parameters<typeof renderWithProviders>[1] = {}) {
  return renderWithProviders(
    <StationDetailPanel
      stationId="STA-01"
      station={station}
      qualityRow={qualityRow}
      onClose={() => {}}
    />,
    overrides,
  );
}

describe("StationDetailPanel", () => {
  beforeEach(() => {
    resetQueueCache();
    clearQueue();
  });

  it("renders the score together with its breakdown and its reason codes", async () => {
    renderPanel();

    expect(await screen.findByTestId("trust-chip")).toHaveTextContent("0.51");

    // Standing rule 9 on screen: never a bare number.
    const breakdown = await screen.findByTestId("trust-breakdown");
    expect(within(breakdown).getByText(/Sensor health/i)).toBeInTheDocument();
    expect(within(breakdown).getByText(/Cross-sensor consistency/i)).toBeInTheDocument();

    const reasons = screen.getByTestId("station-reason-codes");
    expect(within(reasons).getAllByTestId("reason-code-badge").length).toBeGreaterThan(0);
  });

  it("states reason codes as plain-language sentences, not codes alone", async () => {
    renderPanel();
    const reasons = await screen.findByTestId("station-reason-codes");
    expect(
      within(reasons).getByText(/Trust is reduced by readings near or beyond their physical bounds/i),
    ).toBeInTheDocument();
    expect(within(reasons).getByText(/Trust is reduced by 7 active defect\(s\)/i)).toBeInTheDocument();
  });

  it("marks the imputation term as a placeholder", async () => {
    renderPanel();
    expect(await screen.findByTestId("placeholder-marker")).toBeInTheDocument();
  });

  it("shows a coverage note for a structurally absent parameter", async () => {
    renderPanel({
      routes: {
        "/v1/defects": page([
          fixtures.defect({
            id: 9,
            reason_code: "R18",
            station_id: "STA-01",
            parameter: "Wind_Speed",
            counts_toward_rate: false,
            evidence: { parameter: "Wind_Speed" },
          }),
        ]),
      },
    });

    const coverage = await screen.findByTestId("station-coverage-facts");
    expect(within(coverage).getByText(/does not carry a Wind_Speed sensor/i)).toBeInTheDocument();
    expect(within(coverage).getByText(/excluded from the defect rate/i)).toBeInTheDocument();
  });

  it("draws a sparkline per parameter and marks the flagged points", async () => {
    renderPanel();
    const sparklines = await screen.findAllByTestId("sparkline");
    expect(sparklines.length).toBeGreaterThan(0);
    // The readings fixture flags one point and drops one, so the series is broken
    // rather than interpolated across the gap.
    expect(sparklines.some((node) => Number(node.dataset.flagged) > 0)).toBe(true);
  });

  it("queues an acknowledgement locally and says nothing was sent", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "Acknowledge" }));

    await waitFor(() => expect(screen.getByTestId("queued-actions")).toBeInTheDocument());
    expect(listQueuedActions()).toHaveLength(1);
    expect(listQueuedActions()[0]).toMatchObject({ kind: "acknowledge", stationId: "STA-01" });
    expect(screen.getByText(/Nothing has been sent/i)).toBeInTheDocument();
  });

  it("records the reason codes that were on screen when the operator acted", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByTestId("trust-chip");

    await user.click(screen.getByRole("button", { name: "Dispatch" }));

    await waitFor(() => expect(listQueuedActions()).toHaveLength(1));
    expect(listQueuedActions()[0]?.reasonCodes).toContain("T04");
  });

  it("shows an actionable error when the score cannot be loaded", async () => {
    const { ApiError } = await import("../api/client");
    renderPanel({
      failures: {
        "/v1/trust/STA-01": new ApiError({
          status: 404,
          title: "Not Found",
          detail: "No trust score for station 'STA-01'. Load a data drop first.",
          requestId: "req-77",
        }),
      },
    });

    const error = await screen.findByTestId("error-state");
    expect(error).toHaveTextContent(/No trust score for station/i);
    expect(error).toHaveTextContent(/Load a data drop first/i);
    expect(error).toHaveTextContent(/req-77/);
    expect(error).not.toHaveTextContent(/something went wrong/i);
  });

  it("prompts for a selection when no station is chosen", () => {
    renderWithProviders(
      <StationDetailPanel stationId={null} station={null} qualityRow={null} onClose={() => {}} />,
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent(/No station selected/i);
  });
});

describe("trust reason codes render as sentences, not templates", () => {
  it("fills every trust placeholder from the score's own evidence", async () => {
    renderPanel();
    const reasons = await screen.findByTestId("station-reason-codes");

    // Before the engine carried its figures, T03 read "disagreement with —
    // neighbouring station(s)" and leaned on the component detail underneath.
    expect(
      within(reasons).getByText(/Trust is reduced by disagreement with 4 neighbouring station\(s\)/i),
    ).toBeInTheDocument();
    expect(within(reasons).queryByText(/—/)).not.toBeInTheDocument();
    expect(within(reasons).queryByTestId("reason-code-detail")).not.toBeInTheDocument();
  });

  it("still shows the component detail for a score written before evidence existed", async () => {
    renderPanel({
      routes: {
        "/v1/trust/STA-01": fixtures.trustScore({
          reason_codes: ["T03"],
          // An older row: components and codes, but no figures.
          evidence: {},
          components: fixtures.trustComponents.map((c) => ({ ...c, evidence: {} })),
        }),
      },
    });

    const reasons = await screen.findByTestId("station-reason-codes");
    expect(within(reasons).getByTestId("reason-code-detail")).toHaveTextContent(
      "3 parameter(s) compared to peers",
    );
    // Degraded, but never a raw brace.
    expect(within(reasons).queryByText(/[{}]/)).not.toBeInTheDocument();
  });
});
