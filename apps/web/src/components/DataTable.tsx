import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

/**
 * A dense, sortable, keyboard-navigable, virtualised table.
 *
 * Written rather than pulled in, for two reasons. First, virtualisation and real
 * table semantics fight each other in most libraries, and the semantics have to
 * win here: this is an operations screen, and it has to be traversable by keyboard
 * and legible to a screen reader. Second, `<tr>` rows inside a scrolling container
 * with spacer rows above and below keeps the markup a genuine `<table>`, so
 * `scope`, `aria-sort`, and row headers all still mean what they say.
 *
 * Rows below the virtualisation threshold render whole, which keeps every unit test
 * and every Playwright assertion looking at real DOM rather than a window.
 */

export interface Column<Row> {
  key: string;
  header: string;
  /** Shown as a native tooltip on the header, for a caveat too long for the label
   * itself (e.g. a provisional/relative figure) - never the only place it is said. */
  headerHint?: string;
  /** Extracted once per row per sort; keep it cheap. */
  sortValue?: (row: Row) => string | number | null;
  render: (row: Row) => ReactNode;
  align?: "left" | "right";
  /** Marks the column whose cell is the row's <th scope="row">. */
  isRowHeader?: boolean;
  width?: string;
}

export type SortDirection = "asc" | "desc";

export interface DataTableProps<Row> {
  rows: readonly Row[];
  columns: readonly Column<Row>[];
  rowKey: (row: Row) => string;
  caption: string;
  onRowActivate?: (row: Row) => void;
  selectedKey?: string | null;
  initialSort?: { key: string; direction: SortDirection };
  emptyMessage?: string;
  rowHeight?: number;
  /** Above this many rows the body virtualises. */
  virtualiseAbove?: number;
  maxBodyHeight?: number;
}

export function DataTable<Row>({
  rows,
  columns,
  rowKey,
  caption,
  onRowActivate,
  selectedKey = null,
  initialSort,
  emptyMessage = "No rows match the current filter.",
  rowHeight = 32,
  virtualiseAbove = 60,
  maxBodyHeight = 480,
}: DataTableProps<Row>) {
  const [sort, setSort] = useState<{ key: string; direction: SortDirection } | null>(
    initialSort ?? null,
  );
  const [scrollTop, setScrollTop] = useState(0);
  const bodyRef = useRef<HTMLDivElement>(null);

  const sorted = useMemo(() => {
    if (!sort) return [...rows];
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return [...rows];
    const extract = column.sortValue;
    const direction = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = extract(a);
      const right = extract(b);
      // Nulls sort last in both directions: "not measured" is not "lowest".
      if (left === null && right === null) return 0;
      if (left === null) return 1;
      if (right === null) return -1;
      if (typeof left === "number" && typeof right === "number") {
        return (left - right) * direction;
      }
      return String(left).localeCompare(String(right)) * direction;
    });
  }, [rows, columns, sort]);

  const toggleSort = useCallback((key: string) => {
    setSort((previous) =>
      previous?.key === key
        ? { key, direction: previous.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
  }, []);

  const virtualise = sorted.length > virtualiseAbove;
  const overscan = 8;
  const visibleCount = Math.ceil(maxBodyHeight / rowHeight) + overscan * 2;
  const startIndex = virtualise
    ? Math.max(0, Math.floor(scrollTop / rowHeight) - overscan)
    : 0;
  const endIndex = virtualise ? Math.min(sorted.length, startIndex + visibleCount) : sorted.length;
  const visible = sorted.slice(startIndex, endIndex);
  const padTop = startIndex * rowHeight;
  const padBottom = Math.max(0, (sorted.length - endIndex) * rowHeight);

  useEffect(() => {
    // A new filter shortens the list; keep the viewport inside it. `scrollTo` is
    // unimplemented in jsdom, so the assignment fallback keeps component tests from
    // dying on a scroll reset that has no visual meaning there anyway.
    setScrollTop(0);
    const body = bodyRef.current;
    if (!body) return;
    if (typeof body.scrollTo === "function") body.scrollTo({ top: 0 });
    else body.scrollTop = 0;
  }, [rows]);

  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: Row) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowActivate?.(row);
    }
  };

  return (
    <div
      ref={bodyRef}
      className="overflow-auto"
      style={{ maxHeight: maxBodyHeight }}
      onScroll={(event) => virtualise && setScrollTop(event.currentTarget.scrollTop)}
      data-testid="data-table-scroll"
    >
      <table className="prov-table" data-testid="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const isSorted = sort?.key === column.key;
              const sortable = Boolean(column.sortValue);
              return (
                <th
                  key={column.key}
                  scope="col"
                  style={column.width ? { width: column.width } : undefined}
                  className={column.align === "right" ? "text-right" : undefined}
                  aria-sort={isSorted ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="flex w-full items-center gap-1 px-3 py-2 text-left font-semibold text-text-secondary hover:text-text"
                      style={column.align === "right" ? { justifyContent: "flex-end" } : undefined}
                      title={column.headerHint}
                    >
                      {column.header}
                      <span aria-hidden="true" className="text-micro">
                        {isSorted ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  ) : (
                    <span className="block px-3 py-2" title={column.headerHint}>
                      {column.header}
                    </span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-5 text-text-tertiary">
                {emptyMessage}
              </td>
            </tr>
          )}
          {padTop > 0 && (
            <tr aria-hidden="true" style={{ height: padTop }}>
              <td colSpan={columns.length} className="border-0 p-0" />
            </tr>
          )}
          {visible.map((row) => {
            const key = rowKey(row);
            const interactive = Boolean(onRowActivate);
            return (
              <tr
                key={key}
                data-testid="data-table-row"
                data-row-key={key}
                aria-selected={selectedKey === key ? true : undefined}
                tabIndex={interactive ? 0 : undefined}
                onClick={interactive ? () => onRowActivate?.(row) : undefined}
                onKeyDown={interactive ? (event) => onRowKeyDown(event, row) : undefined}
                className={interactive ? "cursor-pointer" : undefined}
              >
                {columns.map((column) =>
                  column.isRowHeader ? (
                    <th
                      key={column.key}
                      scope="row"
                      className="px-3 text-left font-normal text-text"
                      style={{ height: rowHeight }}
                    >
                      {column.render(row)}
                    </th>
                  ) : (
                    <td
                      key={column.key}
                      className={[
                        "px-3",
                        column.align === "right" ? "text-right prov-numeric font-mono" : "",
                      ].join(" ")}
                      style={{ height: rowHeight }}
                    >
                      {column.render(row)}
                    </td>
                  ),
                )}
              </tr>
            );
          })}
          {padBottom > 0 && (
            <tr aria-hidden="true" style={{ height: padBottom }}>
              <td colSpan={columns.length} className="border-0 p-0" />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
