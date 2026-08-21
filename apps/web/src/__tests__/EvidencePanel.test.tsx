import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EvidencePanel } from "../features/evidence/EvidencePanel";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders, stubClient } from "../test/harness";

describe("EvidencePanel", () => {
  it("lists the flagged cells", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await waitFor(() =>
      expect(screen.getAllByTestId("data-table-row")).toHaveLength(fixtures.defects.length),
    );
  });

  it("states the reason code as a sentence with the detector's numbers", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const evidence = await screen.findByTestId("defect-evidence");
    expect(
      within(evidence).getByText(/Value of 3000 µg\/m3 exceeds the physical maximum for PM10/),
    ).toBeInTheDocument();
  });

  it("shows the detector's own evidence numbers", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const numbers = await screen.findByTestId("evidence-numbers");
    expect(within(numbers).getByText("value")).toBeInTheDocument();
    expect(within(numbers).getByText("3000")).toBeInTheDocument();
    expect(within(numbers).getByText("max")).toBeInTheDocument();
  });

  it("draws the raw series around the flagged point", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    expect(await screen.findByTestId("evidence-chart")).toBeInTheDocument();
  });

  it("ranks neighbouring stations by real distance, nearest first", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    // The default defect is STA-03 (47.559175, 21.502204). Of the other fixture
    // stations carrying PM10, STA-01 (47.577175, 21.502204) is ~2.0km away and
    // STA-02 (47.577175, 21.520204) is ~2.4km - STA-01 must sort first. STA-04 has
    // no coordinates, so it is ranked last and shown without a distance.
    const heading = await screen.findByText(/Nearest stations measuring/);
    expect(heading).toBeInTheDocument();
    const neighbours = await screen.findAllByTestId("neighbour-series");
    expect(neighbours).toHaveLength(3);
    expect(neighbours[0]).toHaveTextContent("STA-01");
    expect(neighbours[0]).toHaveTextContent("2.0 km");
    expect(neighbours[1]).toHaveTextContent("STA-02");
    expect(neighbours[1]).toHaveTextContent("2.4 km");
    expect(neighbours[2]).toHaveTextContent("STA-04");
    expect(neighbours[2]).not.toHaveTextContent("km");
  });

  it("marks a coverage defect as excluded from the defect rate", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBe(3));
    const coverageRow = screen
      .getAllByTestId("data-table-row")
      .find((row) => row.dataset.rowKey === "3");
    expect(within(coverageRow!).getByText(/no — coverage/i)).toBeInTheDocument();
  });

  it("populates the SHAP slot with the operator sentence and signed bars", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const sentence = await screen.findByTestId("shap-sentence");
    expect(sentence).toHaveTextContent(/Driven primarily by/);
    const bars = await screen.findByTestId("shap-bars");
    expect(within(bars).getByText("boundary_layer_proxy")).toBeInTheDocument();
    const shap = screen.getByTestId("shap-attribution");
    expect(within(shap).getByText(/fault class: physically_impossible/)).toBeInTheDocument();
    // Drawn from a centreline in both directions: the largest bar (boundary_layer_proxy,
    // |-6.2| of a 6.2 max) must stop at 50% of the track, not 100%, or it overruns the
    // card and pushes the label column out of view.
    const widestBar = within(bars).getByTitle(/lowered by -6.200/);
    expect(widestBar).toHaveStyle({ width: "50%" });
  });

  it("degrades the SHAP slot honestly when no model is loaded", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/explain/1": fixtures.explainDegraded },
    });
    const degraded = await screen.findByTestId("shap-degraded");
    expect(degraded).toHaveTextContent(/statistics layer alone/);
  });

  it("uses the backend's own note for a rule-decided defect, not a generic filler", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/explain/1": fixtures.explainRuleFallback },
    });
    const degraded = await screen.findByTestId("shap-degraded");
    // Wind_Speed isn't a deweathered pollutant, so the backend's note names that
    // specifically - the fix under test is that this real reason renders instead of
    // the old hardcoded "(physical)" filler, which would be wrong for a non-physical
    // rule like this one.
    expect(degraded).toHaveTextContent(/Wind_Speed is not covered by the deweather model/);
    expect(degraded).not.toHaveTextContent(/physical\)/);
  });

  it("draws the before/after deweathering chart, toggleable", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const toggle = await screen.findByTestId("deweather-toggle");
    const residualButton = within(toggle).getByRole("button", { name: "Residual" });
    expect(within(toggle).getByRole("button", { name: "Both" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(residualButton);
    expect(residualButton).toHaveAttribute("aria-pressed", "true");
  });

  it("labels the raw and residual lines with a legend", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const chart = await screen.findByTestId("deweather-chart");
    expect(await within(chart).findByText("Raw")).toBeInTheDocument();
    expect(within(chart).getByText("Residual")).toBeInTheDocument();
  });

  it("shows a degraded deweather note when no residuals are stored", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/deweather/STA-03": fixtures.deweatherDegraded },
    });
    expect(await screen.findByText(/Deweathered residual for PM10/)).toBeInTheDocument();
  });

  it("shows the HST-GAT's own reason when the attention overlay is not available", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const slots = await screen.findAllByTestId("not-yet-computed");
    expect(
      slots.some((slot) => slot.textContent?.includes("HST-GAT has not been trained")),
    ).toBe(true);
  });

  it("draws the learned attention edges touching this station when the overlay is available", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/graph/attention": fixtures.attentionOverlayAvailable },
    });
    const attention = await screen.findByTestId("graph-attention");
    expect(within(attention).getByText(/target PM10/)).toBeInTheDocument();
    const edges = within(attention).getByTestId("attention-edges");
    // The default selected defect is STA-03, which the fixture's wind_conditioned
    // relation names as an edge to STA-02.
    expect(within(edges).getByText(/STA-02/)).toBeInTheDocument();
    // The weight is printed beside the bar, not only reachable by hovering.
    expect(within(edges).getByText("0.310")).toBeInTheDocument();
  });

  it("caps the attention edge list and says how many more were left out", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/graph/attention": fixtures.attentionOverlayManyEdges },
    });
    const attention = await screen.findByTestId("graph-attention");
    const edges = within(attention).getByTestId("attention-edges");
    expect(within(edges).getAllByRole("listitem")).toHaveLength(8);
    expect(within(attention).getByTestId("attention-edges-truncated")).toHaveTextContent(
      "Showing the strongest 8 of 12 edges touching STA-03.",
    );
  });

  it("points to the event timeline for the adjudication verdict", async () => {
    // The defect view is the statistical evidence; the plume-vs-fault verdict is
    // adjudicated per event over the wind graph, and lives on the timeline.
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    expect(await screen.findByTestId("evidence-verdict")).toHaveTextContent(
      "decided per event on the timeline",
    );
  });

  it("selects a different defect when its row is activated", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBe(3));

    const row = screen
      .getAllByTestId("data-table-row")
      .find((candidate) => candidate.dataset.rowKey === "2")!;
    await user.click(row);

    const evidence = await screen.findByTestId("defect-evidence");
    await waitFor(() =>
      expect(
        within(evidence).getByText(/PM2\.5 \(41\.2\) exceeds PM10 \(38\)/),
      ).toBeInTheDocument(),
    );
  });

  it("filters by severity", async () => {
    const user = userEvent.setup();
    const requested: Record<string, unknown>[] = [];
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      onRequest: (path, query) => {
        if (path === "/v1/defects" && query) requested.push(query);
      },
    });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBe(3));

    await user.selectOptions(screen.getByTestId("evidence-severity-filter"), "critical");
    await waitFor(() =>
      expect(requested.some((query) => query.severity === "critical")).toBe(true),
    );
  });

  it("explains an empty ledger as a result, not a blank screen", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: { "/v1/defects": page([]) },
    });
    expect(await screen.findByTestId("empty-state")).toHaveTextContent(/which is itself a result/i);
  });

  it("says the absence is the defect when a flag has no series to draw", async () => {
    renderWithProviders(<EvidencePanel />, {
      route: "/evidence",
      routes: {
        "/v1/defects": page([fixtures.defect({ reason_code: "R01" })]),
        "/v1/readings": page([]),
      },
    });
    expect(await screen.findByText(/That absence is the defect/i)).toBeInTheDocument();
  });
});

describe("the dense code chip is not a downgrade", () => {
  it("carries the row's filled sentence in its tooltip and screen-reader text", async () => {
    // The sentence sites were fixed when the placeholder leak was found; the code
    // chip in the defect table was not, so it read "Value of — — exceeds the
    // physical maximum for —" next to a row holding every one of those numbers.
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBe(3));

    const row = screen
      .getAllByTestId("data-table-row")
      .find((candidate) => candidate.dataset.rowKey === "1")!;
    const chip = within(row).getByTestId("reason-code-badge");

    expect(chip).toHaveAttribute(
      "title",
      "Value of 3000 µg/m3 exceeds the physical maximum for PM10.",
    );
    expect(within(chip).getByText(/^R07: Value of 3000 µg\/m3/)).toBeInTheDocument();
  });

  it("still degrades to an em dash where a tally has no single row to draw on", async () => {
    // The audit report's per-code tally aggregates many defects, so there is no one
    // evidence dict to attach. An em dash is correct there - what must never appear
    // is a brace.
    const { renderReasonSentenceParts } = await import("../api/reason-codes");
    const { text } = renderReasonSentenceParts("R07", {});
    expect(text).toContain("—");
    expect(text).not.toMatch(/[{}]/);
  });
});

describe("truncation is surfaced, never silent", () => {
  it("tells the operator when the ledger walk hit its page cap", async () => {
    // A client whose defect pages never run out: every response offers another
    // cursor, so the walk stops only at the cap. That is the case flag B was about -
    // a count that silently becomes a prefix. The stub is synchronous, so walking
    // the full 100-page cap is a few milliseconds.
    const base = stubClient();
    let served = 0;
    const client = {
      config: base.config,
      get: (async (path: string, options?: Parameters<typeof base.get>[1]) => {
        if (path === "/v1/defects") {
          served += 1;
          return { items: [fixtures.defect({ id: served })], next_cursor: `more-${served}`, count: 1 };
        }
        return base.get(path, options);
      }) as typeof base.get,
    } as typeof base;

    renderWithProviders(<EvidencePanel />, { route: "/evidence", client });

    const banner = await screen.findByTestId("evidence-truncated");
    expect(banner).toHaveTextContent(/Showing the first .* flagged cells/i);
    expect(banner).toHaveTextContent(/narrow by station, code, or time window/i);
  });

  it("shows no truncation banner when the walk reaches the end", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await screen.findByTestId("defect-table");
    expect(screen.queryByTestId("evidence-truncated")).not.toBeInTheDocument();
  });
});
