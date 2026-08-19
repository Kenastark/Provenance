import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ProvEvent } from "../api/client";
import { EventTimeline } from "../features/timeline/EventTimeline";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

function adjudicatedEvent(verdict: string, overrides: Partial<ProvEvent> = {}): ProvEvent {
  const corroborated = verdict === "GENUINE_EVENT";
  return fixtures.provEvent({
    timestamp_utc: "2026-05-12T00:00:00",
    verdict,
    evidence: {
      value: 3000,
      unit: "µg/m3",
      parameter: "PM10",
      adjudication: {
        verdict,
        confidence: corroborated ? 1.0 : 0.5,
        confidence_band: corroborated ? "high" : "moderate",
        routes_to_review: verdict === "AMBIGUOUS",
        evidence: {
          wind: { from_deg: 270, to_deg: 90, speed: 5, speed_unit: "m/s", provenance: "station-local" },
          downwind_neighbours: [
            {
              station_id: "STA-04",
              distance_km: 3,
              bearing_deg: 90,
              edge_weight: 0.39,
              wind_provenance: "station-local",
              carries_parameter: true,
              arrival_delay_min: 10,
              expected_excess: 93,
              actual_excess: corroborated ? 93 : 0,
              corroborated,
            },
          ],
          series: { timestamps: ["2026-05-12T00:00:00", "2026-05-12T01:00:00"], expected: [0, 93], actual: [0, corroborated ? 93 : 0] },
          match_score: corroborated ? 1.0 : 0.35,
          n_downwind: 2,
          n_usable: 2,
          covariates: [
            { name: "traffic", state: "unavailable", reason: "Enclod unconfirmed" },
            { name: "weather", state: "wind-only", reason: "deweathering lands in phase 5" },
          ],
          reason_codes: [corroborated ? "R22" : "R23"],
          notes: ["No headline accuracy figure is reported."],
        },
      },
    },
    ...overrides,
  });
}

describe("adjudication on the timeline", () => {
  it("colours the verdict chip by the verdict", async () => {
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: { "/v1/events": page([adjudicatedEvent("GENUINE_EVENT")]) },
    });
    const chip = await screen.findByTestId("event-verdict");
    expect(chip).toHaveTextContent("Genuine plume");
    expect(chip).toHaveAttribute("data-verdict-kind", "genuine");
  });

  it("opens the evidence bundle when an event is selected", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: { "/v1/events": page([adjudicatedEvent("GENUINE_EVENT")]) },
    });
    await user.click(await screen.findByTestId("event-adjudication-toggle"));
    const detail = await screen.findByTestId("adjudication-detail");
    expect(detail).toBeInTheDocument();
    expect(screen.getByTestId("adjudication-verdict")).toHaveTextContent("Genuine plume");
    expect(screen.getByTestId("adjudication-neighbours")).toBeInTheDocument();
    expect(screen.getByTestId("adjudication-neighbour")).toHaveAttribute("data-station", "STA-04");
    // The covariate stubs are named and explained, never silently omitted.
    expect(screen.getByTestId("adjudication-covariates")).toHaveTextContent("traffic");
    expect(screen.getByTestId("adjudication-covariates")).toHaveTextContent("weather");
  });

  it("marks an ambiguous verdict as routed to review, never a confident call", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: { "/v1/events": page([adjudicatedEvent("AMBIGUOUS")]) },
    });
    await user.click(await screen.findByTestId("event-adjudication-toggle"));
    expect(await screen.findByTestId("adjudication-review")).toBeInTheDocument();
    expect(screen.getByTestId("adjudication-verdict")).toHaveTextContent("Ambiguous");
  });

  it("shows a pending note for an unadjudicated event", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: { "/v1/events": page([fixtures.provEvent({ timestamp_utc: "2026-05-12T00:00:00" })]) },
    });
    await user.click(await screen.findByTestId("event-adjudication-toggle"));
    expect(await screen.findByTestId("adjudication-pending")).toBeInTheDocument();
  });
});
