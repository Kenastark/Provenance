import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EventTimeline, eventMark, eventTone, plotEvents } from "../features/timeline/EventTimeline";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

describe("event plotting", () => {
  const start = new Date("2026-05-01T00:00:00Z");
  const end = new Date("2026-05-03T00:00:00Z");

  it("places an event proportionally along the axis", () => {
    const { plotted } = plotEvents(
      [fixtures.provEvent({ timestamp_utc: "2026-05-02T00:00:00" })],
      start,
      end,
    );
    expect(plotted[0]?.position).toBeCloseTo(0.5);
  });

  it("puts a degenerate axis at the midpoint rather than dividing by zero", () => {
    const at = new Date("2026-05-01T00:00:00Z");
    const { plotted } = plotEvents([fixtures.provEvent()], at, at);
    expect(plotted[0]?.position).toBe(0.5);
  });

  it("derives the axis from the events when the window is unbounded", () => {
    const { start: derivedStart, end: derivedEnd } = plotEvents(fixtures.events, null, null);
    expect(derivedStart).not.toBeNull();
    expect(derivedEnd).not.toBeNull();
    expect(derivedStart!.getTime()).toBeLessThan(derivedEnd!.getTime());
  });

  it("gives categories distinct shapes so colour is not the only channel", () => {
    const physical = eventMark(fixtures.provEvent({ reason_code: "R07" }));
    const statistical = eventMark(fixtures.provEvent({ reason_code: "R12" }));
    const structural = eventMark(fixtures.provEvent({ reason_code: "R02" }));
    expect(new Set([physical, statistical, structural]).size).toBe(3);
  });

  it("tones an event by its severity", () => {
    expect(eventTone(fixtures.provEvent({ severity: "critical" }))).toBe("fault");
    expect(eventTone(fixtures.provEvent({ severity: "medium" }))).toBe("degraded");
    expect(eventTone(fixtures.provEvent({ severity: "info", reason_code: "R20" }))).toBe("neutral");
  });
});

describe("EventTimeline", () => {
  it("plots every event in the window and lists it", async () => {
    renderWithProviders(<EventTimeline />, { route: "/timeline" });
    await waitFor(() =>
      expect(screen.getAllByTestId("timeline-mark")).toHaveLength(fixtures.events.length),
    );
    expect(screen.getAllByTestId("timeline-event")).toHaveLength(fixtures.events.length);
  });

  it("says pending adjudication and never invents a verdict", async () => {
    renderWithProviders(<EventTimeline />, { route: "/timeline" });
    const verdicts = await screen.findAllByTestId("event-verdict");
    for (const verdict of verdicts) {
      expect(verdict).toHaveTextContent("pending adjudication");
    }
    expect(screen.queryByText(/confirmed|refuted|adjudicated/i)).not.toBeInTheDocument();
  });

  it("shows the verdict once the backend supplies one", async () => {
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: {
        "/v1/events": page([
          fixtures.provEvent({ timestamp_utc: "2026-05-12T00:00:00", verdict: "sensor fault" }),
        ]),
      },
    });
    expect(await screen.findByTestId("event-verdict")).toHaveTextContent("sensor fault");
  });

  it("states each event in plain language", async () => {
    renderWithProviders(<EventTimeline />, { route: "/timeline" });
    expect(
      await screen.findByText(/Value of 3000 µg\/m3 exceeds the physical maximum for PM10/),
    ).toBeInTheDocument();
  });

  it("excludes events outside the selected window", async () => {
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: {
        "/v1/events": page([
          // The window is 7 days back from the newest reading (2026-05-14T23:00),
          // so this one is three weeks stale and must not be plotted.
          fixtures.provEvent({ id: 9, timestamp_utc: "2026-04-20T00:00:00" }),
          fixtures.provEvent({ id: 10, timestamp_utc: "2026-05-12T00:00:00" }),
        ]),
      },
    });
    await waitFor(() => expect(screen.getAllByTestId("timeline-mark")).toHaveLength(1));
    expect(screen.getByTestId("timeline-mark")).toHaveAttribute("data-event-id", "10");
  });

  it("offers an empty state rather than a blank axis", async () => {
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: { "/v1/events": page([]) },
    });
    expect(await screen.findByTestId("empty-state")).toHaveTextContent(/No events in this window/i);
  });

  it("names each mark for assistive technology", async () => {
    renderWithProviders(<EventTimeline />, { route: "/timeline" });
    const marks = await screen.findAllByTestId("timeline-mark");
    for (const mark of marks) {
      expect(mark.getAttribute("aria-label")).toMatch(/pending adjudication/);
    }
  });

  it("says 'not applicable' — not 'pending' — for an event with no rise to propagate", async () => {
    // An outage was adjudicated over and found to have no plume question. Telling the
    // operator to run `prov graph adjudicate-db` here would be advice they have already
    // taken, about an event that is settled.
    renderWithProviders(<EventTimeline />, {
      route: "/timeline",
      routes: {
        "/v1/events": page([
          fixtures.provEvent({
            id: 42,
            timestamp_utc: "2026-05-12T00:00:00",
            verdict: null,
            evidence: {
              missing_ticks: 3,
              adjudication_not_applicable: {
                basis: "no_reading_at_event_time",
                reason: "There is no reading here, so there is no rise for the wind to carry.",
              },
            },
          }),
        ]),
      },
    });
    const chip = await screen.findByTestId("event-verdict");
    expect(chip).toHaveTextContent(/not applicable/i);
    expect(chip).not.toHaveTextContent(/pending/i);
    expect(chip).toHaveAttribute("data-verdict-kind", "not_applicable");
  });

  it("explains the non-applicability in the detail pane instead of the pending message", async () => {
    renderWithProviders(<EventTimeline />, {
      route: "/timeline?event=42",
      routes: {
        "/v1/events": page([
          fixtures.provEvent({
            id: 42,
            timestamp_utc: "2026-05-12T00:00:00",
            verdict: null,
            evidence: {
              adjudication_not_applicable: {
                basis: "no_reading_at_event_time",
                reason: "There is no reading here, so there is no rise for the wind to carry.",
              },
            },
          }),
        ]),
      },
    });
    const pane = await screen.findByTestId("adjudication-not-applicable");
    expect(pane).toHaveTextContent(/no rise for the wind to carry/i);
    expect(screen.queryByTestId("adjudication-pending")).not.toBeInTheDocument();
  });
});
