import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { StationDetailPanel } from "../features/station/StationDetailPanel";
import { resetSignoffCache } from "../lib/signoffs";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

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
    resetSignoffCache();
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

  it("says no adjudicated alert exists yet when the station has no event", async () => {
    renderPanel({ routes: { "/v1/events": page([]) } });

    const notice = await screen.findByTestId("no-active-event");
    expect(notice).toHaveTextContent(/No adjudicated alert exists yet/i);
    expect(within(notice).getByRole("link", { name: /Alert Centre/i })).toHaveAttribute(
      "href",
      "/alerts",
    );
    expect(screen.queryByTestId("station-signoff")).not.toBeInTheDocument();
  });

  it("wires Acknowledge/Dispatch to the station's adjudicated event through the real sign-off gate", async () => {
    const user = userEvent.setup();
    const event = fixtures.provEvent({
      id: 42,
      station_id: "STA-01",
      headline: "PM10 at STA-01, above the physical maximum",
    });
    renderPanel({
      routes: { "/v1/events": page([event]) },
      postRoutes: { "/v1/decision/signoff": signoffRoute, "/v1/decision/dispatch": dispatchRoute },
    });

    const panel = await screen.findByTestId("station-signoff");
    expect(within(panel).getByText(/PM10 at STA-01, above the physical maximum/)).toBeInTheDocument();
    expect(within(panel).getByTestId("dispatch-button")).toBeDisabled();

    await user.click(within(panel).getByRole("button", { name: /record sign-off/i }));
    await waitFor(() => expect(within(panel).getByTestId("dispatch-button")).not.toBeDisabled());

    await user.click(within(panel).getByTestId("dispatch-button"));

    const success = await screen.findByTestId("dispatch-success");
    expect(success).toHaveTextContent(/Status sent/);
  });

  it("picks the most notable of several events and links to the Alert Centre for the rest", async () => {
    renderPanel({
      routes: {
        "/v1/events": page([
          fixtures.provEvent({ id: 1, rank: 2, station_id: "STA-01", headline: "Lower-ranked event" }),
          fixtures.provEvent({ id: 2, rank: 1, station_id: "STA-01", headline: "Top-ranked event" }),
        ]),
      },
    });

    const panel = await screen.findByTestId("station-signoff");
    expect(within(panel).getByText(/Top-ranked event/)).toBeInTheDocument();
    expect(within(panel).queryByText(/Lower-ranked event/)).not.toBeInTheDocument();
    expect(within(panel).getByText(/2 adjudicated events/)).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /Open in Alert Centre/i })).toHaveAttribute(
      "href",
      "/alerts?event=2",
    );
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
