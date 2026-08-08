import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AuditReportView, tallyByCode } from "../features/audit/AuditReportView";
import * as fixtures from "../test/fixtures";
import { page, renderWithProviders } from "../test/harness";

describe("tallyByCode", () => {
  it("counts defects per code, most frequent first", () => {
    const tallies = tallyByCode([
      { reason_code: "R07", counts_toward_rate: true },
      { reason_code: "R07", counts_toward_rate: true },
      { reason_code: "R18", counts_toward_rate: false },
    ]);
    expect(tallies[0]).toMatchObject({ code: "R07", count: 2, countsTowardRate: true });
    expect(tallies[1]).toMatchObject({ code: "R18", count: 1, countsTowardRate: false });
  });

  it("takes 'counts toward the rate' from the registry, not from the row", () => {
    // A coverage code is excluded no matter what a row claims: the registry is the
    // single source of truth for what inflates the defect rate.
    const tallies = tallyByCode([{ reason_code: "R18", counts_toward_rate: true }]);
    expect(tallies[0]?.countsTowardRate).toBe(false);
  });
});

describe("AuditReportView", () => {
  it("shows the headline numbers straight off the run", async () => {
    renderWithProviders(<AuditReportView />, { route: "/audit" });
    const headline = await screen.findByTestId("audit-headline");

    expect(within(headline).getByText("4,032")).toBeInTheDocument();
    expect(within(headline).getByText("99.95%")).toBeInTheDocument();
    expect(within(headline).getByText("20.199%")).toBeInTheDocument();
    expect(within(headline).getByText("812")).toBeInTheDocument();
  });

  it("puts the deceptive completeness figure next to the defect rate", async () => {
    renderWithProviders(<AuditReportView />, { route: "/audit" });
    const headline = await screen.findByTestId("audit-headline");
    expect(
      within(headline).getByText(/By this measure the network is healthy/i),
    ).toBeInTheDocument();
  });

  it("displays the defect-rate definition beside the number", async () => {
    renderWithProviders(<AuditReportView />, { route: "/audit" });
    const definition = await screen.findByTestId("defect-rate-definition");

    expect(definition).toHaveTextContent(/Defective cells ÷ covered cells/i);
    expect(definition).toHaveTextContent(/excluded from.*both.*numerator and the denominator/i);
    expect(definition).toHaveTextContent("812 ÷ 4,020 = 20.199%");
  });

  it("breaks the defects down by code and marks the coverage ones", async () => {
    renderWithProviders(<AuditReportView />, { route: "/audit" });
    await waitFor(() => expect(screen.getAllByTestId("data-table-row").length).toBeGreaterThan(0));

    const rows = screen.getAllByTestId("data-table-row");
    const coverageRow = rows.find((row) => row.dataset.rowKey === "R18");
    expect(coverageRow).toBeDefined();
    expect(within(coverageRow!).getByText(/no — coverage/i)).toBeInTheDocument();
  });

  it("links each code to its evidence", async () => {
    renderWithProviders(<AuditReportView />, { route: "/audit" });
    const links = await screen.findAllByRole("link", { name: /drill down/i });
    expect(links[0]).toHaveAttribute("href", expect.stringContaining("/evidence?code="));
  });

  it("explains an empty run rather than showing a blank report", async () => {
    renderWithProviders(<AuditReportView />, {
      route: "/audit",
      routes: { "/v1/audit/runs": page([]) },
    });
    expect(await screen.findByTestId("empty-state")).toHaveTextContent(/No audit run/i);
  });

  it("calls a zero-defect run a result rather than an empty screen", async () => {
    renderWithProviders(<AuditReportView />, {
      route: "/audit",
      routes: { "/v1/defects": page([]) },
    });
    expect(await screen.findByTestId("empty-state")).toHaveTextContent(/is a result/i);
  });

  it("lets an older run be chosen when there is more than one", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuditReportView />, {
      route: "/audit",
      routes: {
        "/v1/audit/runs": page([
          fixtures.auditRun(),
          fixtures.auditRun({ id: "run-older", generated_at: "2026-05-01T00:00:00", n_rows: 10 }),
        ]),
      },
    });

    const select = await screen.findByTestId("audit-run-select");
    await user.selectOptions(select, "run-older");
    await waitFor(() => expect(screen.getByTestId("audit-headline")).toHaveTextContent("10"));
  });
});
