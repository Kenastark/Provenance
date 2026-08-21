import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAlerts } from "../../api/queries";
import type { AlertItem } from "../../api/operations";
import { DataTable, type Column } from "../../components/DataTable";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatPercent, formatTimestamp } from "../../lib/format";
import { verdictMeta } from "../../lib/verdict";
import { AlertDetail } from "./AlertDetail";
import { MaintenanceQueue } from "./MaintenanceQueue";
import { VerdictChip } from "../timeline/EventTimeline";

/**
 * The Alert Centre: everything ranked by RISK, not by certainty.
 *
 * That word matters more than any other on this screen. An adjudicator that is
 * only 55% sure a plume is genuine, sitting over a school and a transit
 * interchange, has to outrank a sensor the adjudicator is 95% sure has failed in
 * an empty field - because the *consequence* of being wrong is what an operator
 * has to weigh, and certainty alone hides that. `alert.risk_factors` is exactly
 * that argument made numeric (`genuineness × exposure × hazard × confidence
 * weight`), and the Severity and Exposure columns sit beside Risk here specifically
 * so the inversion is visible in the list, not just discoverable by opening a row.
 */

export function AlertCentre() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("event");
  const [filter, setFilter] = useState("");

  const alerts = useAlerts();
  const items = useMemo(() => alerts.data?.items ?? [], [alerts.data]);

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (item) =>
        item.station_id.toLowerCase().includes(needle) ||
        item.parameter.toLowerCase().includes(needle) ||
        item.headline.toLowerCase().includes(needle),
    );
  }, [items, filter]);

  const selected = useMemo(
    () => items.find((item) => String(item.event_id) === selectedId) ?? null,
    [items, selectedId],
  );

  const select = (item: AlertItem | null) =>
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (item === null) next.delete("event");
      else next.set("event", String(item.event_id));
      return next;
    });

  const columns: Column<AlertItem>[] = useMemo(
    () => [
      {
        key: "station",
        header: "Station · parameter",
        isRowHeader: true,
        sortValue: (row) => `${row.station_id} ${row.parameter}`,
        render: (row) => (
          <span className="font-mono">
            {row.station_id} · {row.parameter}
          </span>
        ),
      },
      {
        key: "headline",
        header: "Headline",
        render: (row) => <span className="truncate">{row.headline}</span>,
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (row) => row.severity,
        render: (row) => row.severity,
      },
      {
        key: "verdict",
        header: "Verdict",
        sortValue: (row) => verdictMeta(row.verdict).label,
        render: (row) => <VerdictChip verdict={row.verdict} />,
      },
      {
        key: "exposure",
        header: "Exposure",
        align: "right",
        sortValue: (row) => row.exposure,
        render: (row) => row.exposure.toFixed(2),
      },
      {
        key: "confidence",
        header: "Confidence",
        align: "right",
        sortValue: (row) => row.confidence,
        render: (row) => formatPercent(row.confidence * 100, 0),
      },
      {
        key: "risk",
        header: "Risk",
        align: "right",
        sortValue: (row) => row.risk,
        render: (row) => <strong className="prov-numeric font-mono">{row.risk.toFixed(3)}</strong>,
      },
      {
        key: "when",
        header: "When",
        sortValue: (row) => row.timestamp_utc,
        render: (row) => formatTimestamp(row.timestamp_utc),
      },
    ],
    [],
  );

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4" aria-label="Alert Centre">
      {/* Not `flex-1`: this section and the maintenance panel below it are both
          natural-height blocks stacked in a page that scrolls as a whole (the
          outer div's `overflow-y-auto`). Two siblings both fighting for `flex-1`
          inside that scrolling flex column squash to an even split of whatever
          height happens to be available rather than their content height, which
          let the maintenance panel visually overlap the alert rows above it and
          intercept clicks meant for them. */}
      <section aria-labelledby="alert-centre-heading" className="flex flex-col gap-3 lg:flex-row">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <header className="flex flex-wrap items-end gap-3">
            <div className="flex-1">
              <h2 id="alert-centre-heading" className="text-heading">
                Alert Centre
              </h2>
              <p className="text-caption text-text-tertiary">
                {alerts.data
                  ? alerts.data.note
                  : "Candidate events ranked by consequence-weighted risk, not by certainty."}
              </p>
            </div>
            <label className="flex items-center gap-2 text-caption text-text-tertiary">
              <span>Filter</span>
              <input
                className="prov-input"
                type="search"
                value={filter}
                placeholder="station, parameter, headline"
                onChange={(event) => setFilter(event.target.value)}
                data-testid="alerts-filter"
              />
            </label>
          </header>

          {alerts.isLoading && <LoadingState label="Loading alerts" />}
          {alerts.error && (
            <ErrorState error={alerts.error} what="load the ranked alert list" onRetry={alerts.refetch} />
          )}
          {!alerts.isLoading && !alerts.error && items.length === 0 && (
            <div className="prov-panel">
              <EmptyState
                title="No candidate alerts"
                description="Load a data drop and run the audit (`make demo`) to populate the Alert Centre. Alerts are drawn from adjudicated and pending events, not raised independently."
              />
            </div>
          )}
          {items.length > 0 && (
            <div className="prov-panel min-h-0 min-w-0 flex-1 overflow-hidden">
              <DataTable
                rows={filtered}
                columns={columns}
                rowKey={(row) => String(row.event_id)}
                caption="Alerts ranked by risk, with the severity and exposure factors behind the rank"
                initialSort={{ key: "risk", direction: "desc" }}
                selectedKey={selectedId}
                onRowActivate={select}
                maxBodyHeight={480}
                emptyMessage="No alert matches this filter."
              />
            </div>
          )}
        </div>

        <aside
          className={
            selected
              ? "w-full min-w-0 shrink-0 border-t border-border bg-bg-raised pt-1 lg:w-[420px] lg:border-l lg:border-t-0 lg:pt-0"
              : "hidden w-full min-w-0 shrink-0 border-t border-border bg-bg-raised lg:flex lg:w-[420px] lg:border-l lg:border-t-0"
          }
          aria-label="Alert detail"
        >
          <div className="min-w-0 flex-1 overflow-y-auto">
            <AlertDetail alert={selected} />
          </div>
        </aside>
      </section>

      <div className="prov-panel p-4">
        <MaintenanceQueue />
      </div>
    </div>
  );
}
