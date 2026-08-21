import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  useMaintenanceItem,
  useMaintenanceQueue,
  useMaintenanceTransition,
  useRebuildMaintenance,
} from "../../api/queries";
import { ApiError } from "../../api/client";
import {
  MAINTENANCE_STATUSES,
  MAINTENANCE_TRANSITIONS,
  type MaintenanceStatus,
} from "../../api/operations";
import { evidenceFor } from "../../api/reason-codes";
import { DataTable, type Column } from "../../components/DataTable";
import { FactorBreakdown, type Factor } from "../../components/FactorBreakdown";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatCount, formatTimestamp } from "../../lib/format";
import { ROLE_LABELS, useRole } from "../../lib/role";

/**
 * The maintenance queue and its lifecycle: open → acknowledged → dispatched →
 * resolved, forward-only (`ops/maintenance.py::VALID_TRANSITIONS` - acknowledged
 * can also resolve directly, a false alarm needs no dispatch step). Tickets are
 * not raised automatically; "Rebuild queue" calls the same idempotent endpoint the
 * CLI would, so a fresh audit run's flags actually reach this screen.
 */

const STATUS_LABEL: Record<MaintenanceStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  dispatched: "Dispatched",
  resolved: "Resolved",
};

const STATUS_TONE: Record<MaintenanceStatus, string> = {
  open: "prov-state-fault",
  acknowledged: "prov-state-degraded",
  dispatched: "prov-state-degraded",
  resolved: "prov-state-verified",
};

export function MaintenanceQueue() {
  const { role } = useRole();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("item");
  const [statusFilter, setStatusFilter] = useState<MaintenanceStatus | "all">("all");

  const queue = useMaintenanceQueue(statusFilter === "all" ? undefined : statusFilter);
  const item = useMaintenanceItem(selectedId ? Number(selectedId) : undefined);
  const rebuild = useRebuildMaintenance();
  const transition = useMaintenanceTransition();

  const rows = useMemo(() => queue.data?.items ?? [], [queue.data]);

  const select = (id: number | null) =>
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (id === null) next.delete("item");
      else next.set("item", String(id));
      return next;
    });

  const columns: Column<(typeof rows)[number]>[] = useMemo(
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
        key: "code",
        header: "Reason",
        render: (row) => <ReasonCodeBadge code={row.reason_code} variant="code" evidence={evidenceFor(row)} />,
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (row) => row.severity,
        render: (row) => row.severity,
      },
      {
        key: "priority",
        header: "Priority",
        align: "right",
        sortValue: (row) => row.priority,
        render: (row) => row.priority.toFixed(2),
      },
      {
        key: "status",
        header: "Status",
        sortValue: (row) => row.status,
        render: (row) => <span className={STATUS_TONE[row.status]}>{STATUS_LABEL[row.status]}</span>,
      },
      {
        key: "updated",
        header: "Updated",
        sortValue: (row) => row.updated_at,
        render: (row) => formatTimestamp(row.updated_at),
      },
    ],
    [],
  );

  // Not `h-full flex-1`: embedded inside AlertCentre's naturally-scrolling page
  // rather than filling a bounded viewport on its own - see the note on
  // AlertCentre's alert-list section for why that combination overlapped
  // siblings instead of stacking them.
  return (
    <section className="flex flex-col gap-3 lg:flex-row" aria-label="Maintenance queue">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <h3 className="text-heading">Maintenance queue</h3>
            <p className="text-caption text-text-tertiary">
              {rows.length} ticket{rows.length === 1 ? "" : "s"}
              {queue.data?.truncated ? " (truncated at the traversal cap)" : ""} · raised from fault
              classifications, ranked by priority (severity × station importance).
            </p>
          </div>
          <label className="flex items-center gap-2 text-caption text-text-tertiary">
            <span>Status</span>
            <select
              className="prov-input"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as MaintenanceStatus | "all")}
              data-testid="maintenance-status-filter"
            >
              <option value="all">All</option>
              {MAINTENANCE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABEL[status]}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="prov-button"
            onClick={() => rebuild.mutate()}
            disabled={rebuild.isPending}
            data-testid="maintenance-rebuild"
          >
            {rebuild.isPending ? "Rebuilding…" : "Rebuild from latest run"}
          </button>
        </header>
        {rebuild.isSuccess && (
          <p className="text-caption prov-state-verified" role="status">
            {rebuild.data.created} new ticket{rebuild.data.created === 1 ? "" : "s"} raised from run{" "}
            {rebuild.data.audit_run_id}.
          </p>
        )}
        {rebuild.isError && (
          <p className="text-caption prov-state-fault" role="alert">
            {rebuild.error instanceof ApiError ? rebuild.error.detail : "The rebuild failed."}
          </p>
        )}

        {queue.isLoading && <LoadingState label="Loading the maintenance queue" />}
        {queue.error && (
          <ErrorState error={queue.error} what="load the maintenance queue" onRetry={queue.refetch} />
        )}
        {!queue.isLoading && !queue.error && rows.length === 0 && (
          <div className="prov-panel">
            <EmptyState
              title="The queue is empty"
              description="No tickets exist for this run yet. Rebuild from the latest run to raise tickets for its fault classifications."
            />
          </div>
        )}
        {rows.length > 0 && (
          <div className="prov-panel min-h-0 min-w-0 flex-1 overflow-hidden">
            <DataTable
              rows={rows}
              columns={columns}
              rowKey={(row) => String(row.id)}
              caption="Maintenance tickets by priority and lifecycle status"
              initialSort={{ key: "priority", direction: "desc" }}
              selectedKey={selectedId}
              onRowActivate={(row) => select(row.id)}
              maxBodyHeight={420}
              emptyMessage="No ticket matches this filter."
            />
          </div>
        )}
      </div>

      <aside
        className="w-full min-w-0 shrink-0 border-t border-border pt-3 lg:w-[320px] lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0"
        aria-label="Maintenance ticket detail"
      >
        {!selectedId && (
          <EmptyState
            title="No ticket selected"
            description="Choose a row to see its priority breakdown, its transition history, and the next allowed status."
          />
        )}
        {selectedId && item.isLoading && <LoadingState label="Loading ticket" />}
        {selectedId && item.error && (
          <ErrorState error={item.error} what="load this ticket" onRetry={item.refetch} />
        )}
        {item.data && <TicketDetail ticket={item.data} actor={ROLE_LABELS[role]} onTransition={transition} />}
      </aside>
    </section>
  );
}

function TicketDetail({
  ticket,
  actor,
  onTransition,
}: {
  ticket: NonNullable<ReturnType<typeof useMaintenanceItem>["data"]>;
  actor: string;
  onTransition: ReturnType<typeof useMaintenanceTransition>;
}) {
  const factors: Factor[] = [
    { key: "severity_weight", label: "Severity weight", value: ticket.severity_weight },
    {
      key: "importance",
      label: "Station importance (rel.)",
      value: ticket.importance,
      hint: "PopulationExposure, provisional: min-max normalised across the stations in the current drop, not an absolute figure - not comparable across two different networks without renormalising.",
    },
  ];
  const next = MAINTENANCE_TRANSITIONS[ticket.status];

  return (
    <div className="flex flex-col gap-4" data-testid="maintenance-ticket-detail">
      <div>
        <h4 className="text-subhead">
          {ticket.station_id} · {ticket.parameter}
        </h4>
        {/* Not `ticket.headline`: the backend bakes one sentence per ticket, but a
            ticket aggregates every flag behind it, and they can carry different
            evidence values (four different PM2.5-over-PM10 readings, say) - there
            is no single number to substitute, so the backend's own headline can
            arrive with its placeholders unfilled. Routing through the same badge
            every other screen uses degrades that honestly to an em dash instead
            of leaking a raw `{token}` onto the screen. */}
        <div className="mt-1">
          <ReasonCodeBadge code={ticket.reason_code} variant="sentence" evidence={evidenceFor(ticket)} />
        </div>
        <p className="mt-1 text-caption text-text-tertiary">
          {formatCount(ticket.n_flags)} flagged cell{ticket.n_flags === 1 ? "" : "s"} behind this
          ticket{ticket.n_flags > 1 ? " - the sentence above may not fit every one" : ""}.
        </p>
      </div>

      <FactorBreakdown value={ticket.priority} valueLabel="Priority" factors={factors} formula="priority = severity weight × station importance" />

      <div>
        <h5 className="mb-1 text-caption uppercase tracking-wide text-text-tertiary">Next status</h5>
        {next.length === 0 ? (
          <p className="text-caption text-text-tertiary">Resolved — this is a terminal state.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {next.map((status) => (
              <button
                key={status}
                type="button"
                className="prov-button"
                disabled={onTransition.isPending}
                onClick={() => onTransition.mutate({ id: ticket.id, to: status, actor })}
                data-testid={`transition-${status}`}
              >
                Mark {STATUS_LABEL[status].toLowerCase()}
              </button>
            ))}
          </div>
        )}
        {onTransition.isError && (
          <p className="mt-2 text-caption prov-state-fault" role="alert">
            {onTransition.error instanceof ApiError
              ? onTransition.error.detail
              : "The transition failed."}
          </p>
        )}
      </div>

      <div>
        <h5 className="mb-1 text-caption uppercase tracking-wide text-text-tertiary">History</h5>
        {!ticket.history || ticket.history.length === 0 ? (
          <p className="text-caption text-text-tertiary">No transitions recorded yet.</p>
        ) : (
          <ol className="m-0 list-none space-y-1 p-0 text-caption text-text-secondary" data-testid="ticket-history">
            {ticket.history.map((entry, index) => (
              <li key={index}>
                {entry.from_status ? `${STATUS_LABEL[entry.from_status]} → ` : ""}
                {STATUS_LABEL[entry.to_status]} by {entry.actor} at {formatTimestamp(entry.at)}
                {entry.note ? ` — ${entry.note}` : ""}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
