import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { QualityMonitor, buildQualityRows } from "../features/quality/QualityMonitor";
import * as fixtures from "../test/fixtures";
import { renderWithProviders } from "../test/harness";

function rowIds(): string[] {
  return screen
    .getAllByTestId("data-table-row")
    .map((row) => row.dataset.rowKey ?? "")
    .filter(Boolean);
}

describe("row building", () => {
  // Uptime and last-calibration are served by /v1/quality/summary now (computed in
  // io/db/repository.py::quality_summary), not derived here - buildRows is just the
  // station/meta join. The formula's assumptions are pinned on the backend in
  // tests/unit/test_uptime_assumptions.py.
  it("joins each quality station to its station metadata", () => {
    const rows = buildQualityRows(
      [fixtures.qualityStation({ station_id: "STA-01" })],
      [fixtures.station({ station_id: "STA-01", name: "Nagyerdő" })],
    );
    expect(rows[0]?.meta?.name).toBe("Nagyerdő");
  });

  it("leaves meta undefined when a station has no matching metadata row", () => {
    const rows = buildQualityRows([fixtures.qualityStation({ station_id: "STA-99" })], []);
    expect(rows[0]?.meta).toBeUndefined();
  });
});

describe("QualityMonitor", () => {
  it("renders one row per station in the run", async () => {
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds()).toHaveLength(fixtures.qualitySummary.stations.length));
  });

  it("sorts by a column when its header is activated", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    await user.click(screen.getByRole("button", { name: /Station/i }));
    expect(rowIds()).toEqual(["STA-01", "STA-02", "STA-03", "STA-04"]);

    await user.click(screen.getByRole("button", { name: /Station/i }));
    expect(rowIds()).toEqual(["STA-04", "STA-03", "STA-02", "STA-01"]);
  });

  it("marks the sorted column for assistive technology", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    await user.click(screen.getByRole("button", { name: /Flags/i }));
    const header = screen.getByRole("columnheader", { name: /Flags/i });
    expect(header).toHaveAttribute("aria-sort", "ascending");
  });

  it("sorts unscored stations last in both directions, not as the lowest score", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    // The table opens sorted by trust ascending: worst first, so the station that
    // needs attention is at the top.
    await waitFor(() => expect(rowIds()).toEqual(["STA-03", "STA-01", "STA-02", "STA-04"]));

    // STA-04 has no score at all. "Not measured" is not "lowest", so it stays at the
    // bottom when the sort flips rather than jumping to the top.
    await user.click(screen.getByRole("button", { name: /Trust/i }));
    expect(rowIds()).toEqual(["STA-02", "STA-01", "STA-03", "STA-04"]);
  });

  it("filters by free text", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    await user.type(screen.getByTestId("quality-filter"), "STA-02");
    await waitFor(() => expect(rowIds()).toEqual(["STA-02"]));
  });

  it("filters by trust state", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    await user.selectOptions(screen.getByTestId("quality-state-filter"), "fault");
    await waitFor(() => expect(rowIds()).toEqual(["STA-03"]));
  });

  it("says so when a filter matches nothing", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    await user.type(screen.getByTestId("quality-filter"), "no-such-station");
    await waitFor(() =>
      expect(screen.getByText(/No station matches this filter/i)).toBeInTheDocument(),
    );
  });

  it("opens the station detail from a row, by keyboard", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

    const row = screen.getAllByTestId("data-table-row")[0]!;
    row.focus();
    await user.keyboard("{Enter}");

    const panel = await screen.findByTestId("station-detail-panel");
    expect(within(panel).getByRole("heading", { level: 2 })).toHaveTextContent(/STA-/);
  });

  it("uses tabular numerals wherever numbers stack", async () => {
    renderWithProviders(<QualityMonitor />);
    await waitFor(() => expect(rowIds().length).toBeGreaterThan(0));
    expect(screen.getByTestId("data-table")).toHaveClass("prov-table");
  });

  it("renders the served uptime and calibration figures as given, not re-derived", async () => {
    renderWithProviders(<QualityMonitor />, {
      routes: {
        "/v1/quality/summary": {
          audit_run_id: "run-2026-05-15",
          stations: [
            fixtures.qualityStation({
              station_id: "STA-01",
              uptime_pct: 87.5,
              absent_cells: 5,
              expected_cells: 40,
              last_calibration_at: "2026-05-09T00:00:00",
            }),
          ],
        },
      },
    });
    await waitFor(() => expect(rowIds()).toEqual(["STA-01"]));
    expect(screen.getByText("87.50%")).toBeInTheDocument();
    expect(screen.getByTitle("5 absent of 40 expected cells")).toBeInTheDocument();
  });

  it("shows an em dash for uptime and 'none detected' for calibration when neither is served", async () => {
    renderWithProviders(<QualityMonitor />, {
      routes: {
        "/v1/quality/summary": {
          audit_run_id: "run-2026-05-15",
          stations: [
            fixtures.qualityStation({
              station_id: "STA-01",
              uptime_pct: null,
              absent_cells: 0,
              expected_cells: null,
              last_calibration_at: null,
            }),
          ],
        },
      },
    });
    await waitFor(() => expect(rowIds()).toEqual(["STA-01"]));
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("none detected")).toBeInTheDocument();
  });
});
