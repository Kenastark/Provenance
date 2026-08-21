import { useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import { useAdminStatus, useModelDrift, useRequestRetrain } from "../../api/queries";
import type { AdminDispatchSummary, AdminAuditRunSummary } from "../../api/operations";
import { DataTable, type Column } from "../../components/DataTable";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatCount, formatRateAsPercent, formatTimestamp } from "../../lib/format";
import { useInfraMetrics } from "./infraMetrics";
import { ModelDriftPanels } from "./ModelDriftPanels";
import { RbacMatrix } from "./RbacMatrix";

/**
 * The Admin screen: who can do what (RBAC), what version and config is running,
 * and the two-plane monitor - infra health from `/metrics`, model/data health from
 * `/v1/admin/model-drift`. Kept as separate sections rather than one merged
 * "health" view, matching the deliberate separation the backend itself documents
 * (`api/routers/admin.py`'s own docstring on `model_drift`).
 */

function InfraHealthPanel() {
  const metrics = useInfraMetrics();
  return (
    <div className="prov-panel p-4" data-testid="infra-health-panel">
      <h4 className="text-subhead">Infra plane</h4>
      <p className="mt-1 text-caption text-text-tertiary">
        Parsed from <code>/metrics</code> (Prometheus exposition format), the same series a
        Prometheus/Grafana stack would scrape. Full detail belongs there; this is the headline.
      </p>
      {metrics.isLoading && <LoadingState label="Reading /metrics" />}
      {metrics.error && (
        <ErrorState error={metrics.error} what="read the /metrics endpoint" onRetry={metrics.refetch} />
      )}
      {metrics.data && (
        <dl className="mt-3 grid grid-cols-3 gap-3 text-center">
          <div>
            <dt className="text-caption text-text-tertiary">Service</dt>
            <dd
              className={
                metrics.data.up === null
                  ? "text-body text-text-tertiary"
                  : metrics.data.up
                    ? "text-body prov-state-verified"
                    : "text-body prov-state-fault"
              }
            >
              {metrics.data.up === null ? "unknown" : metrics.data.up ? "up" : "down"}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-text-tertiary">Requests served</dt>
            <dd className="prov-numeric font-mono text-body">{formatCount(metrics.data.requestsTotal)}</dd>
          </div>
          <div>
            <dt className="text-caption text-text-tertiary">In flight</dt>
            <dd className="prov-numeric font-mono text-body">{formatCount(metrics.data.requestsInFlight)}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

function RetrainControls({ triggers }: { triggers: Record<string, string> }) {
  const retrain = useRequestRetrain();
  const [lastTarget, setLastTarget] = useState<string | null>(null);

  return (
    <div>
      <h4 className="mb-1 text-subhead">Retraining triggers</h4>
      <p className="mb-2 text-caption text-text-tertiary">
        Requesting a retrain records the request; it does not run a training job inline. The command
        below is what an operator runs to act on it.
      </p>
      <ul className="m-0 list-none space-y-2 p-0">
        {Object.entries(triggers).map(([target, command]) => (
          <li key={target} className="flex flex-wrap items-center gap-2">
            <span className="w-[96px] font-mono text-caption text-text-secondary">{target}</span>
            <code className="text-caption text-text-tertiary">{command}</code>
            <button
              type="button"
              className="prov-button"
              disabled={retrain.isPending}
              onClick={() => {
                setLastTarget(target);
                retrain.mutate({ target });
              }}
              data-testid={`retrain-${target}`}
            >
              Request retrain
            </button>
          </li>
        ))}
      </ul>
      {retrain.isSuccess && lastTarget && (
        <p className="mt-2 text-caption prov-state-verified" role="status">
          Recorded: {retrain.data.note} (queued {formatTimestamp(retrain.data.queued_at)})
        </p>
      )}
      {retrain.isError && (
        <p className="mt-2 text-caption prov-state-fault" role="alert">
          {retrain.error instanceof ApiError ? retrain.error.detail : "The request could not be recorded."}
        </p>
      )}
    </div>
  );
}

function StatusSection() {
  const status = useAdminStatus();

  const runColumns: Column<AdminAuditRunSummary>[] = useMemo(
    () => [
      { key: "id", header: "Run", isRowHeader: true, render: (row) => <span className="font-mono">{row.id}</span> },
      { key: "generated", header: "Generated", render: (row) => formatTimestamp(row.generated_at) },
      { key: "rows", header: "Rows", align: "right", render: (row) => formatCount(row.n_rows) },
      { key: "rate", header: "Defect rate", align: "right", render: (row) => formatRateAsPercent(row.defect_rate) },
      { key: "config", header: "Config hash", render: (row) => <span className="font-mono">{row.config_hash.slice(0, 10)}</span> },
    ],
    [],
  );

  const dispatchColumns: Column<AdminDispatchSummary>[] = useMemo(
    () => [
      { key: "id", header: "Dispatch", isRowHeader: true, render: (row) => <span className="font-mono">{row.dispatch_id}</span> },
      { key: "event", header: "Event", align: "right", render: (row) => row.event_id },
      { key: "channel", header: "Channel", render: (row) => row.channel },
      { key: "status", header: "Status", render: (row) => row.status },
      { key: "when", header: "Dispatched", render: (row) => formatTimestamp(row.dispatched_at) },
    ],
    [],
  );

  if (status.isLoading) return <LoadingState label="Loading admin status" />;
  if (status.error) return <ErrorState error={status.error} what="load admin status" onRetry={status.refetch} />;
  if (!status.data) return null;
  const data = status.data;

  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="prov-panel p-3">
          <dt className="text-caption text-text-tertiary">Version</dt>
          <dd className="font-mono text-body">{data.version}</dd>
        </div>
        <div className="prov-panel p-3">
          <dt className="text-caption text-text-tertiary">Config hash</dt>
          <dd className="font-mono text-body">{data.config_hashes.config_hash.slice(0, 10)}</dd>
        </div>
        <div className="prov-panel p-3">
          <dt className="text-caption text-text-tertiary">Trust config hash</dt>
          <dd className="font-mono text-body">{data.config_hashes.trust_config_hash.slice(0, 10)}</dd>
        </div>
        <div className="prov-panel p-3">
          <dt className="text-caption text-text-tertiary">Maintenance</dt>
          <dd className="text-body">
            {formatCount(data.maintenance_summary.open)} open of {formatCount(data.maintenance_summary.total)}
          </dd>
        </div>
      </dl>

      <div>
        <h4 className="mb-1 text-subhead">Model versions</h4>
        <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-caption text-text-secondary">
          {Object.entries(data.model_versions).map(([model, version]) => (
            <li key={model}>
              <span className="text-text-tertiary">{model}</span> <span className="font-mono">{version}</span>
            </li>
          ))}
        </ul>
      </div>

      <RetrainControls triggers={data.retraining_triggers} />

      <div>
        <h4 className="mb-1 text-subhead">Audit runs</h4>
        {data.audit_runs.length === 0 ? (
          <p className="text-caption text-text-tertiary">No audit run stored yet.</p>
        ) : (
          <DataTable
            rows={data.audit_runs}
            columns={runColumns}
            rowKey={(row) => row.id}
            caption="Recent audit runs"
            maxBodyHeight={240}
          />
        )}
      </div>

      <div>
        <h4 className="mb-1 text-subhead">Dispatch history</h4>
        <p className="mb-2 text-caption text-text-tertiary">{data.export_history.note}</p>
        {data.export_history.dispatches.length === 0 ? (
          <p className="text-caption text-text-tertiary">No dispatch has been sent yet.</p>
        ) : (
          <DataTable
            rows={data.export_history.dispatches}
            columns={dispatchColumns}
            rowKey={(row) => row.dispatch_id}
            caption="Recent dispatches"
            maxBodyHeight={240}
          />
        )}
      </div>
    </div>
  );
}

export function AdminDashboard() {
  const drift = useModelDrift();

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4" aria-label="Admin">
      <header>
        <h2 className="text-heading">Admin</h2>
        <p className="text-caption text-text-tertiary">
          Access control, running configuration, and the two-plane monitor - infra health and
          model/data health, kept separate on purpose.
        </p>
      </header>

      <section aria-labelledby="admin-rbac-heading" className="prov-panel p-4">
        <h3 id="admin-rbac-heading" className="mb-3 text-heading">
          Access control
        </h3>
        <RbacMatrix />
      </section>

      <section aria-labelledby="admin-status-heading" className="prov-panel p-4">
        <h3 id="admin-status-heading" className="mb-3 text-heading">
          Status
        </h3>
        <StatusSection />
      </section>

      <section aria-labelledby="admin-monitoring-heading" className="flex flex-col gap-4">
        <h3 id="admin-monitoring-heading" className="text-heading">
          Monitoring
        </h3>
        <InfraHealthPanel />
        <div className="prov-panel p-4">
          <h4 className="mb-1 text-subhead">Model plane</h4>
          {drift.isLoading && <LoadingState label="Loading model drift" />}
          {drift.error && (
            <ErrorState error={drift.error} what="load the model drift report" onRetry={drift.refetch} />
          )}
          {!drift.isLoading && !drift.error && !drift.data && (
            <EmptyState title="No drift report" description="The model plane has nothing to report yet." />
          )}
          {drift.data && <ModelDriftPanels report={drift.data} />}
        </div>
      </section>
    </div>
  );
}
