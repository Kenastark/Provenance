import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AuditRun } from "../../api/client";
import { REASON_CODES, reasonCode } from "../../api/reason-codes";
import { useAuditRun, useAuditRuns, useDefects } from "../../api/queries";
import { DataTable, type Column } from "../../components/DataTable";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatCount, formatPercent, formatRateAsPercent, formatTimestamp } from "../../lib/format";

/**
 * The phase-1 audit report, rendered natively.
 *
 * The headline strip is the whole pitch in four numbers, and the order matters:
 * conventional completeness first (the number that says the network is healthy),
 * the defect rate second (the number that says it is not). Neither is written down
 * anywhere - both come off the audit run row, computed by the engine from the data.
 *
 * The defect rate's definition is displayed *next to* the number rather than in a
 * footnote, because the definition is the claim. A defect rate that quietly counted
 * structural absences would be a bigger, more impressive, and wrong number.
 */

interface CodeTally {
  code: string;
  name: string;
  count: number;
  countsTowardRate: boolean;
  severity: string;
  category: string;
}

export function tallyByCode(defects: readonly { reason_code: string; counts_toward_rate: boolean }[]): CodeTally[] {
  const counts = new Map<string, number>();
  for (const defect of defects) {
    counts.set(defect.reason_code, (counts.get(defect.reason_code) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([code, count]) => {
      const def = reasonCode(code);
      return {
        code,
        name: def?.name ?? "UNKNOWN",
        count,
        countsTowardRate: def?.countsTowardDefectRate ?? false,
        severity: def?.severity ?? "info",
        category: def?.category ?? "unknown",
      };
    })
    .sort((a, b) => b.count - a.count || a.code.localeCompare(b.code));
}

function Headline({ run }: { run: AuditRun }) {
  const cells = [
    {
      label: "Readings audited",
      value: formatCount(run.n_rows),
      note: "Rows in the loaded drop.",
    },
    {
      label: "Conventional completeness",
      value: formatPercent(run.conventional_completeness_pct),
      note: "What every other dashboard reports. By this measure the network is healthy.",
    },
    {
      label: "Defect rate",
      value: formatRateAsPercent(run.defect_rate),
      note: `${formatCount(run.n_defective_cells)} defective of ${formatCount(run.n_covered_cells)} covered cells.`,
      emphasis: true,
    },
    {
      label: "Defective cells",
      value: formatCount(run.n_defective_cells),
      note: "Present, well-formed, plausible, and wrong.",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="audit-headline">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className={["prov-panel p-4", cell.emphasis ? "border-border-strong" : ""].join(" ")}
        >
          <p className="text-caption uppercase tracking-wide text-text-tertiary">{cell.label}</p>
          <p className="prov-numeric mt-1 font-mono text-display-l text-text">{cell.value}</p>
          <p className="mt-1 text-caption text-text-secondary">{cell.note}</p>
        </div>
      ))}
    </div>
  );
}

export function AuditReportView() {
  const runs = useAuditRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const latest = useMemo(() => {
    if (!runs.data || runs.data.length === 0) return null;
    return [...runs.data].sort((a, b) => b.generated_at.localeCompare(a.generated_at))[0] ?? null;
  }, [runs.data]);

  const runId = selectedRunId ?? latest?.id;
  const run = useMemo(() => runs.data?.find((r) => r.id === runId) ?? latest, [runs.data, runId, latest]);
  const detail = useAuditRun(runId);
  const defects = useDefects({ limit: 500 });

  const tallies = useMemo(() => tallyByCode(defects.data ?? []), [defects.data]);
  const truncated = (defects.data?.length ?? 0) >= 500;

  const columns: Column<CodeTally>[] = useMemo(
    () => [
      {
        key: "code",
        header: "Code",
        isRowHeader: true,
        sortValue: (row) => row.code,
        render: (row) => <ReasonCodeBadge code={row.code} variant="code" />,
      },
      { key: "name", header: "Name", sortValue: (row) => row.name, render: (row) => row.name },
      {
        key: "category",
        header: "Category",
        sortValue: (row) => row.category,
        render: (row) => row.category,
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (row) => row.severity,
        render: (row) => row.severity,
      },
      {
        key: "count",
        header: "Count",
        align: "right",
        sortValue: (row) => row.count,
        render: (row) => formatCount(row.count),
      },
      {
        key: "counts",
        header: "In defect rate",
        sortValue: (row) => (row.countsTowardRate ? 1 : 0),
        render: (row) =>
          row.countsTowardRate ? (
            "yes"
          ) : (
            <span className="text-text-tertiary">no — coverage</span>
          ),
      },
      {
        key: "drill",
        header: "",
        render: (row) => (
          <Link className="text-interactive" to={`/evidence?code=${encodeURIComponent(row.code)}`}>
            Drill down
          </Link>
        ),
      },
    ],
    [],
  );

  if (runs.isLoading) return <LoadingState label="Loading audit runs" />;
  if (runs.error) {
    return <ErrorState error={runs.error} what="load the audit runs" onRetry={runs.refetch} />;
  }
  if (!run) {
    return (
      <div className="p-4">
        <div className="prov-panel">
          <EmptyState
            title="No audit run has been recorded"
            description="Run `make demo` to bring up the stack, load the fixture corpus, and audit it. The report renders from the stored run, so it needs one to exist."
          />
        </div>
      </div>
    );
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4" aria-label="Audit report">
      <header className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <h2 className="text-heading">Audit report</h2>
          <p className="text-caption text-text-tertiary">
            Run {run.id} · generated {formatTimestamp(run.generated_at)} · code {run.code_version} ·
            config {run.config_hash.slice(0, 10)} · data {run.data_checksum.slice(0, 10)}
          </p>
        </div>
        {(runs.data?.length ?? 0) > 1 && (
          <label className="flex items-center gap-2 text-caption text-text-tertiary">
            <span>Run</span>
            <select
              className="prov-input"
              value={runId ?? ""}
              onChange={(event) => setSelectedRunId(event.target.value)}
              data-testid="audit-run-select"
            >
              {(runs.data ?? []).map((option) => (
                <option key={option.id} value={option.id}>
                  {formatTimestamp(option.generated_at)}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      <Headline run={run} />

      {/* The definition sits with the number, not in a footnote. */}
      <div className="prov-panel p-4" data-testid="defect-rate-definition">
        <h3 className="text-subhead">How the defect rate is defined</h3>
        <p className="mt-1 text-body text-text-secondary">
          Defective cells ÷ covered cells. A cell is one (station, parameter, hour). Structural
          absences — a station that never carried a given sensor — are excluded from{" "}
          <em>both</em> the numerator and the denominator, and are reported separately as coverage
          facts. Counting them as defects would inflate this number without a single extra thing
          being wrong with the network.
        </p>
        <p className="prov-numeric mt-2 font-mono text-body text-text">
          {formatCount(run.n_defective_cells)} ÷ {formatCount(run.n_covered_cells)} ={" "}
          {formatRateAsPercent(run.defect_rate)}
        </p>
      </div>

      <div className="prov-panel p-4">
        <h3 className="mb-2 text-subhead">Defect breakdown by reason code</h3>
        {defects.isLoading && <LoadingState label="Loading the defect ledger" />}
        {defects.error && (
          <ErrorState error={defects.error} what="load the defect ledger" onRetry={defects.refetch} />
        )}
        {defects.data && tallies.length === 0 && (
          <EmptyState
            title="The audit found no defects in this run"
            description="That is a result, not an empty screen: every covered cell passed every detector."
          />
        )}
        {tallies.length > 0 && (
          <>
            <DataTable
              rows={tallies}
              columns={columns}
              rowKey={(row) => row.code}
              caption="Defect counts by reason code"
              initialSort={{ key: "count", direction: "desc" }}
              maxBodyHeight={420}
            />
            {truncated && (
              <p className="mt-2 text-caption text-text-tertiary">
                The ledger was truncated at the API's 500-row page limit, so these counts are a
                lower bound. The run header above is computed over every row.
              </p>
            )}
          </>
        )}
      </div>

      {detail.data?.summary && (
        <details className="prov-panel p-4">
          <summary className="cursor-pointer text-subhead">Stored run summary</summary>
          <pre className="mt-3 overflow-x-auto text-code text-text-secondary">
            {JSON.stringify(detail.data.summary, null, 2)}
          </pre>
        </details>
      )}

      <p className="text-caption text-text-tertiary">
        Registry: {Object.keys(REASON_CODES).length} reason codes, of which{" "}
        {Object.values(REASON_CODES).filter((code) => code.countsTowardDefectRate).length} count
        toward the defect rate.
      </p>
    </section>
  );
}
