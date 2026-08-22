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

/**
 * The engine's own per-code tally, computed over every row when the audit ran.
 *
 * `summary.defects_by_code` is the authoritative count. The alternative - counting
 * the rows the paginated ledger returns - is wrong the moment a run exceeds one
 * page, which the 18-station demo corpus already does: R10 is 336 in the engine's
 * tally and 145 on the first page, and seven codes never appear at all.
 */
export function tallyFromSummary(summary: Record<string, unknown> | undefined): CodeTally[] | null {
  const raw = summary?.["defects_by_code"];
  if (!raw || typeof raw !== "object") return null;
  const entries = Object.entries(raw as Record<string, unknown>).filter(
    ([, count]) => typeof count === "number",
  ) as [string, number][];
  return entries.length > 0 ? buildTallies(new Map(entries)) : null;
}

export function tallyByCode(defects: readonly { reason_code: string; counts_toward_rate: boolean }[]): CodeTally[] {
  const counts = new Map<string, number>();
  for (const defect of defects) {
    counts.set(defect.reason_code, (counts.get(defect.reason_code) ?? 0) + 1);
  }
  return buildTallies(counts);
}

function buildTallies(counts: Map<string, number>): CodeTally[] {
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

interface NetworkWideFinding {
  reasonCode: string;
  parameter: string;
  stationCount: number;
  flaggedReadings: number;
  totalReadings: number;
  fraction: number;
}

/**
 * A (reason_code, parameter) pair the audit engine found firing on every station
 * that carries that parameter - a single systemic fact about a whole channel (a
 * mislabelled unit, say) rather than thousands of individual per-reading defects.
 * `summary.network_wide_findings` is computed generically by the engine (never a
 * hardcoded code or parameter here); this just parses the untyped summary blob the
 * same defensive way `tallyFromSummary` does.
 */
export function networkWideFindingsFromSummary(
  summary: Record<string, unknown> | undefined,
): NetworkWideFinding[] | null {
  const raw = summary?.["network_wide_findings"];
  if (!Array.isArray(raw)) return null;
  const findings: NetworkWideFinding[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const r = item as Record<string, unknown>;
    if (
      typeof r.reason_code !== "string" ||
      typeof r.parameter !== "string" ||
      typeof r.station_count !== "number" ||
      typeof r.flagged_readings !== "number" ||
      typeof r.total_readings !== "number" ||
      typeof r.fraction !== "number"
    ) {
      continue;
    }
    findings.push({
      reasonCode: r.reason_code,
      parameter: r.parameter,
      stationCount: r.station_count,
      flaggedReadings: r.flagged_readings,
      totalReadings: r.total_readings,
      fraction: r.fraction,
    });
  }
  return findings;
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

  // The authoritative tally comes off the stored run summary. The ledger is only a
  // fallback for a run recorded before the summary carried one, and in that case
  // the screen says the counts are a lower bound.
  const authoritative = useMemo(
    () => tallyFromSummary(detail.data?.summary),
    [detail.data],
  );
  const networkWideFindings = useMemo(
    () => networkWideFindingsFromSummary(detail.data?.summary),
    [detail.data],
  );
  // Only reach for the ledger once the summary has settled *without* a tally.
  // Rendering a provisional count while the authoritative one is still in flight
  // would flash a wrong breakdown - and a wrong number that corrects itself a
  // moment later is worse than a spinner, because someone may have read it.
  const summarySettled = detail.isFetched || detail.isError || !runId;
  const needsLedger = summarySettled && authoritative === null;
  const defects = useDefects({ limit: 500, enabled: needsLedger });

  const tallies = useMemo(
    () => authoritative ?? (needsLedger ? tallyByCode(defects.data?.items ?? []) : []),
    [authoritative, needsLedger, defects.data],
  );
  // The fallback counts a fetched ledger, which the cursor walk now reports as
  // truncated directly rather than being inferred from a page-size heuristic.
  const truncated = needsLedger && (defects.data?.truncated ?? false);

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

      {summarySettled && networkWideFindings && (
        <div className="prov-panel p-4" data-testid="network-wide-findings">
          <h3 className="text-subhead">Network-wide findings</h3>
          {networkWideFindings.length === 0 ? (
            <p className="mt-1 text-body text-text-secondary">
              None in this run — no reason code fires on every station carrying a given
              parameter.
            </p>
          ) : (
            <>
              <p className="mt-1 text-body text-text-secondary">
                Each row below fires on every station that carries that parameter — a single
                systemic fact about the whole channel, not a station-specific fault. Called out
                separately so it is not read as thousands of unrelated per-reading defects.
              </p>
              <ul className="mt-3 m-0 list-none space-y-2 p-0">
                {networkWideFindings.map((f) => (
                  <li
                    key={`${f.reasonCode}-${f.parameter}`}
                    className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2 last:border-b-0 last:pb-0"
                  >
                    <span className="text-body">
                      <ReasonCodeBadge code={f.reasonCode} variant="code" /> affects{" "}
                      <strong>{f.parameter}</strong> at all {f.stationCount} stations that carry
                      it
                    </span>
                    <Link
                      className="prov-numeric text-caption text-interactive underline"
                      to={`/evidence?code=${encodeURIComponent(f.reasonCode)}`}
                    >
                      {formatCount(f.flaggedReadings)} of {formatCount(f.totalReadings)} readings
                      ({formatRateAsPercent(f.fraction, 1)})
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <div className="prov-panel p-4">
        <h3 className="mb-2 text-subhead">Defect breakdown by reason code</h3>
        {!summarySettled && <LoadingState label="Loading the audit summary" />}
        {needsLedger && defects.isLoading && (
          <LoadingState label="Loading the defect ledger" />
        )}
        {authoritative === null && defects.error && (
          <ErrorState error={defects.error} what="load the defect ledger" onRetry={defects.refetch} />
        )}
        {summarySettled && !defects.isLoading && tallies.length === 0 && (
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
