import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type Column } from "../components/DataTable";

interface Row {
  id: string;
  name: string;
  value: number | null;
}

const columns: Column<Row>[] = [
  {
    key: "name",
    header: "Name",
    isRowHeader: true,
    sortValue: (row) => row.name,
    render: (row) => row.name,
  },
  {
    key: "value",
    header: "Value",
    align: "right",
    sortValue: (row) => row.value,
    render: (row) => row.value ?? "—",
  },
];

function rows(count: number): Row[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `r${index}`,
    name: `Row ${String(index).padStart(3, "0")}`,
    value: index,
  }));
}

function renderTable(data: Row[], overrides: Partial<Parameters<typeof DataTable<Row>>[0]> = {}) {
  return render(
    <DataTable
      rows={data}
      columns={columns}
      rowKey={(row) => row.id}
      caption="Test table"
      {...overrides}
    />,
  );
}

describe("DataTable", () => {
  it("renders every row below the virtualisation threshold", () => {
    renderTable(rows(10));
    expect(screen.getAllByTestId("data-table-row")).toHaveLength(10);
  });

  it("renders only a window of a long list, but keeps the table's full height", () => {
    renderTable(rows(500), { virtualiseAbove: 60, maxBodyHeight: 320, rowHeight: 32 });

    const rendered = screen.getAllByTestId("data-table-row");
    // A window plus overscan — far fewer than 500, and enough to fill the viewport.
    expect(rendered.length).toBeGreaterThan(10);
    expect(rendered.length).toBeLessThan(60);

    // Spacer rows preserve the scroll height so the scrollbar is honest about how
    // much data is below.
    const spacers = screen
      .getByTestId("data-table")
      .querySelectorAll("tr[aria-hidden='true']");
    expect(spacers.length).toBeGreaterThan(0);
  });

  it("sorts the whole list, not just the rendered window", async () => {
    const user = userEvent.setup();
    renderTable(rows(500), { virtualiseAbove: 60 });

    await user.click(screen.getByRole("button", { name: /Value/i }));
    // Ascending: the first rendered row is the global minimum.
    expect(screen.getAllByTestId("data-table-row")[0]).toHaveAttribute("data-row-key", "r0");

    await user.click(screen.getByRole("button", { name: /Value/i }));
    // Descending: the global maximum, which was never in the first window.
    expect(screen.getAllByTestId("data-table-row")[0]).toHaveAttribute("data-row-key", "r499");
  });

  it("sorts nulls last in both directions", async () => {
    const user = userEvent.setup();
    const data: Row[] = [
      { id: "a", name: "A", value: 5 },
      { id: "b", name: "B", value: null },
      { id: "c", name: "C", value: 1 },
    ];
    renderTable(data);

    const order = () =>
      screen.getAllByTestId("data-table-row").map((row) => row.dataset.rowKey);

    await user.click(screen.getByRole("button", { name: /Value/i }));
    expect(order()).toEqual(["c", "a", "b"]);

    await user.click(screen.getByRole("button", { name: /Value/i }));
    expect(order()).toEqual(["a", "c", "b"]);
  });

  it("marks the sorted column with aria-sort", async () => {
    const user = userEvent.setup();
    renderTable(rows(5));

    expect(screen.getByRole("columnheader", { name: /Name/i })).toHaveAttribute(
      "aria-sort",
      "none",
    );
    await user.click(screen.getByRole("button", { name: /Name/i }));
    expect(screen.getByRole("columnheader", { name: /Name/i })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("activates a row by click and by keyboard", async () => {
    const user = userEvent.setup();
    const onRowActivate = vi.fn();
    renderTable(rows(3), { onRowActivate });

    const [first, second] = screen.getAllByTestId("data-table-row");
    await user.click(first!);
    expect(onRowActivate).toHaveBeenCalledWith(expect.objectContaining({ id: "r0" }));

    second!.focus();
    await user.keyboard("{Enter}");
    expect(onRowActivate).toHaveBeenCalledWith(expect.objectContaining({ id: "r1" }));

    await user.keyboard(" ");
    expect(onRowActivate).toHaveBeenCalledTimes(3);
  });

  it("gives rows no tab stop when they do nothing", () => {
    renderTable(rows(3));
    for (const row of screen.getAllByTestId("data-table-row")) {
      expect(row).not.toHaveAttribute("tabindex");
    }
  });

  it("keeps the row's identifying cell as a row header", () => {
    renderTable(rows(1));
    const row = screen.getByTestId("data-table-row");
    expect(within(row).getByRole("rowheader")).toHaveTextContent("Row 000");
  });

  it("says so when there is nothing to show", () => {
    renderTable([], { emptyMessage: "No station matches this filter." });
    expect(screen.getByText("No station matches this filter.")).toBeInTheDocument();
  });

  it("carries an accessible caption", () => {
    renderTable(rows(2), { caption: "Stations by trust" });
    expect(screen.getByRole("table", { name: "Stations by trust" })).toBeInTheDocument();
  });
});
