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

describe("uptime and calibration derivation", () => {
  it("computes uptime from R01 absent cells over expected cells", () => {
    const rows = buildQualityRows(
      [fixtures.qualityStation({ station_id: "STA-01", n_parameters: 2 })],
      [fixtures.station()],
      [
        fixtures.defect({ id: 1, reason_code: "R01", station_id: "STA-01" }),
        fixtures.defect({ id: 2, reason_code: "R01", station_id: "STA-01" }),
      ],
      [],
      10, // ten hours of window
    );

    // 2 absent of (10 hours x 2 parameters) = 20 expected -> 90%.
    expect(rows[0]?.expectedHours).toBe(20);
    expect(rows[0]?.uptimePct).toBeCloseTo(90);
  });

  it("shows no uptime at all rather than a number without a denominator", () => {
    const rows = buildQualityRows([fixtures.qualityStation()], [fixtures.station()], [], [], null);
    expect(rows[0]?.uptimePct).toBeNull();
  });

  it("takes the newest R15 discontinuity as the last calibration epoch", () => {
    const rows = buildQualityRows(
      [fixtures.qualityStation()],
      [fixtures.station()],
      [],
      [
        fixtures.defect({ id: 3, reason_code: "R15", station_id: "STA-01", timestamp_utc: "2026-05-02T00:00:00" }),
        fixtures.defect({ id: 4, reason_code: "R15", station_id: "STA-01", timestamp_utc: "2026-05-09T00:00:00" }),
      ],
      168,
    );
    expect(rows[0]?.lastCalibration).toBe("2026-05-09T00:00:00");
  });

  it("leaves the calibration epoch null when the audit detected none", () => {
    const rows = buildQualityRows([fixtures.qualityStation()], [fixtures.station()], [], [], 168);
    expect(rows[0]?.lastCalibration).toBeNull();
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
});
