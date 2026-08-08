import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EvidencePanel } from "../features/evidence/EvidencePanel";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

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

  it("lists the neighbouring stations measuring the same parameter", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const neighbours = await screen.findAllByTestId("neighbour-series");
    expect(neighbours.length).toBeGreaterThan(0);
    expect(neighbours[0]).toHaveTextContent(/STA-/);
  });

  it("marks a coverage defect as excluded from the defect rate", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBe(3));
    const coverageRow = screen
      .getAllByTestId("data-table-row")
      .find((row) => row.dataset.rowKey === "3");
    expect(within(coverageRow!).getByText(/no — coverage/i)).toBeInTheDocument();
  });

  it("renders the SHAP and attention slots as explicitly not yet computed", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    const slots = await screen.findAllByTestId("not-yet-computed");
    expect(slots).toHaveLength(2);
    expect(slots[0]).toHaveTextContent(/phase 5/);
    expect(slots[1]).toHaveTextContent(/phase 6/);
  });

  it("never shows an adjudication verdict before phase 4", async () => {
    renderWithProviders(<EvidencePanel />, { route: "/evidence" });
    expect(await screen.findByTestId("evidence-verdict")).toHaveTextContent(
      "pending adjudication (phase 4)",
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
