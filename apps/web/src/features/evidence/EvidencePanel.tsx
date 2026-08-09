import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Defect, Explain } from "../../api/client";
import { evidenceFor, REASON_CODES } from "../../api/reason-codes";
import {
  useDefects,
  useDeweather,
  useExplain,
  useReadings,
  useStations,
} from "../../api/queries";
import { DataTable, type Column } from "../../components/DataTable";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { EmptyState, ErrorState, LoadingState, NotYetComputed } from "../../components/States";
import { formatMeasurement, formatTimestamp, toDate } from "../../lib/format";
import { useWindowState } from "../../lib/windowContext";

/**
 * Why a particular reading is wrong.
 *
 * The reason-code sentence, the detector's own evidence numbers, the raw series
 * around the flagged point with the flagged region marked, and the neighbouring
 * stations that contradict it. This screen is the argument; everything else in the
 * dashboard is navigation to it.
 *
 * SHAP (phase 5) and attention (phase 6) get explicit empty slots rather than being
 * hidden, so the finished shape is visible and nobody is tempted to fill them early.
 */

const CONTEXT_HOURS = 24;

export function EvidencePanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const stationFilter = searchParams.get("station") ?? undefined;
  const codeFilter = searchParams.get("code") ?? undefined;
  const selectedId = searchParams.get("defect");
  const { resolved } = useWindowState();
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const defects = useDefects({
    station: stationFilter,
    code: codeFilter,
    severity: severityFilter || undefined,
    start: resolved.start,
    end: resolved.end,
  });
  const stations = useStations();

  const rows = defects.data?.items ?? [];
  const truncated = defects.data?.truncated ?? false;
  const selected = useMemo(
    () => rows.find((defect) => String(defect.id) === selectedId) ?? rows[0] ?? null,
    [rows, selectedId],
  );

  const setParam = (key: string, value: string | null) =>
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });

  const columns: Column<Defect>[] = useMemo(
    () => [
      {
        key: "code",
        header: "Code",
        isRowHeader: true,
        sortValue: (defect) => defect.reason_code,
        // The dense chip still needs the row's evidence: its tooltip and its
        // screen-reader text are the full sentence, and without this they read
        // "Value of — — exceeds the physical maximum for —" beside a row that
        // holds every one of those numbers.
        render: (defect) => (
          <ReasonCodeBadge
            code={defect.reason_code}
            variant="code"
            evidence={evidenceFor(defect)}
          />
        ),
      },
      {
        key: "station",
        header: "Station",
        sortValue: (defect) => defect.station_id,
        render: (defect) => <span className="font-mono">{defect.station_id}</span>,
      },
      {
        key: "parameter",
        header: "Parameter",
        sortValue: (defect) => defect.parameter,
        render: (defect) => defect.parameter,
      },
      {
        key: "when",
        header: "Timestamp (UTC)",
        sortValue: (defect) => defect.timestamp_utc,
        render: (defect) => formatTimestamp(defect.timestamp_utc),
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (defect) => defect.severity,
        render: (defect) => defect.severity,
      },
      {
        key: "counts",
        header: "Counts toward rate",
        sortValue: (defect) => (defect.counts_toward_rate ? 1 : 0),
        render: (defect) =>
          defect.counts_toward_rate ? (
            "yes"
          ) : (
            <span className="text-text-tertiary" title="Coverage facts are excluded from both the numerator and the denominator.">
              no — coverage
            </span>
          ),
      },
    ],
    [],
  );

  if (defects.isLoading || stations.isLoading) return <LoadingState label="Loading defects" />;
  if (defects.error) {
    return <ErrorState error={defects.error} what="load the defect ledger" onRetry={defects.refetch} />;
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
      <header className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <h2 className="text-heading">Evidence</h2>
          <p className="text-caption text-text-tertiary">
            {rows.length} flagged cell{rows.length === 1 ? "" : "s"} in the{" "}
            {resolved.label.toLowerCase()} window.
          </p>
        </div>
        <label className="flex items-center gap-2 text-caption text-text-tertiary">
          <span>Station</span>
          <select
            className="prov-input"
            value={stationFilter ?? ""}
            onChange={(event) => setParam("station", event.target.value || null)}
            data-testid="evidence-station-filter"
          >
            <option value="">All</option>
            {(stations.data ?? []).map((station) => (
              <option key={station.station_id} value={station.station_id}>
                {station.station_id}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-caption text-text-tertiary">
          <span>Code</span>
          <select
            className="prov-input"
            value={codeFilter ?? ""}
            onChange={(event) => setParam("code", event.target.value || null)}
            data-testid="evidence-code-filter"
          >
            <option value="">All</option>
            {Object.values(REASON_CODES)
              .filter((code) => code.category !== "trust")
              .map((code) => (
                <option key={code.code} value={code.code}>
                  {code.code} — {code.name}
                </option>
              ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-caption text-text-tertiary">
          <span>Severity</span>
          <select
            className="prov-input"
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value)}
            data-testid="evidence-severity-filter"
          >
            <option value="">All</option>
            {["critical", "high", "medium", "low", "info"].map((severity) => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </select>
        </label>
      </header>

      {truncated && (
        <p
          className="prov-panel p-2 text-caption prov-state-degraded"
          role="status"
          data-testid="evidence-truncated"
        >
          Showing the first {rows.length.toLocaleString()} flagged cells. There are more than
          this many for these filters — narrow by station, code, or time window to see the rest.
        </p>
      )}

      {rows.length === 0 ? (
        <div className="prov-panel">
          <EmptyState
            title="No defects match these filters"
            description="Clear a filter, widen the time window, or load a data drop with `make demo`. An empty ledger with data loaded means the audit found nothing here — which is itself a result."
          />
        </div>
      ) : (
        <>
          <div className="prov-panel overflow-hidden" data-testid="defect-table">
            <DataTable
              rows={rows}
              columns={columns}
              rowKey={(defect) => String(defect.id)}
              caption="Flagged cells from the latest audit run"
              selectedKey={selected ? String(selected.id) : null}
              onRowActivate={(defect) => setParam("defect", String(defect.id))}
              initialSort={{ key: "when", direction: "desc" }}
              maxBodyHeight={320}
            />
          </div>

          {selected && <DefectEvidence defect={selected} />}
        </>
      )}
    </div>
  );
}

export function DefectEvidence({ defect }: { defect: Defect }) {
  const at = toDate(defect.timestamp_utc);
  const start = at ? new Date(at.getTime() - CONTEXT_HOURS * 3600_000).toISOString() : null;
  const end = at ? new Date(at.getTime() + CONTEXT_HOURS * 3600_000).toISOString() : null;

  const stations = useStations();
  const target = useReadings({
    stationId: defect.station_id,
    parameter: defect.parameter,
    start,
    end,
    limit: 200,
  });

  // The neighbours this reading contradicts: every other station that carries the
  // same parameter. Which of them are *physically connected* is a phase-4 question
  // (that is what the wind-conditioned graph answers); until then the honest claim
  // is "other stations measuring the same thing at the same time".
  const neighbourIds = useMemo(
    () =>
      (stations.data ?? [])
        .filter(
          (station) =>
            station.station_id !== defect.station_id &&
            Object.prototype.hasOwnProperty.call(station.coverage ?? {}, defect.parameter),
        )
        .map((station) => station.station_id)
        .slice(0, 3),
    [stations.data, defect],
  );

  const unit = target.data?.[0]?.unit ?? null;

  const chartData = useMemo(() => {
    return (target.data ?? []).map((reading) => ({
      t: reading.timestamp_utc,
      label: formatTimestamp(reading.timestamp_utc),
      value: reading.value,
      flagged: reading.timestamp_utc === defect.timestamp_utc ? reading.value : null,
    }));
  }, [target.data, defect.timestamp_utc]);

  return (
    <section className="flex flex-col gap-4" aria-label={`Evidence for defect ${defect.id}`} data-testid="defect-evidence">
      <div className="prov-panel p-4">
        <h3 className="text-subhead">
          {defect.station_id} · {defect.parameter}
        </h3>
        <p className="mt-1 text-caption text-text-tertiary">
          {formatTimestamp(defect.timestamp_utc)} · severity {defect.severity} ·{" "}
          {defect.counts_toward_rate
            ? "counts toward the defect rate"
            : "coverage fact, excluded from the defect rate"}
        </p>

        <div className="mt-3">
          <ReasonCodeBadge code={defect.reason_code} evidence={evidenceFor(defect)} />
        </div>

        <h4 className="mb-1 mt-4 text-caption uppercase tracking-wide text-text-tertiary">
          Detector evidence
        </h4>
        {Object.keys(defect.evidence ?? {}).length === 0 ? (
          <p className="text-caption text-text-tertiary">
            This detector recorded no numeric evidence beyond the flag itself.
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-caption" data-testid="evidence-numbers">
            {Object.entries(defect.evidence).map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-text-tertiary">{key}</dt>
                <dd className="prov-numeric m-0 font-mono text-text">
                  {typeof value === "number" ? formatMeasurement(value) : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {/* ------------------------------------------------------ the series */}
      <div className="prov-panel p-4">
        <h4 className="mb-2 text-subhead">
          Raw series, ±{CONTEXT_HOURS}h around the flag
        </h4>
        {target.isLoading && <LoadingState label="Loading the series" />}
        {target.error && (
          <ErrorState error={target.error} what="load the raw series" onRetry={target.refetch} />
        )}
        {target.data && target.data.length === 0 && (
          <EmptyState
            title="No readings around this flag"
            description="The flagged cell is an absence: there is no series to draw because nothing was recorded here. That absence is the defect."
          />
        )}
        {target.data && target.data.length > 0 && (
          <div style={{ width: "100%", height: 220 }} data-testid="evidence-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--prov-chart-grid)" strokeDasharray="2 4" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
                  stroke="var(--prov-chart-grid)"
                  minTickGap={48}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
                  stroke="var(--prov-chart-grid)"
                  width={56}
                  label={
                    unit
                      ? { value: unit, angle: -90, position: "insideLeft", fontSize: 11 }
                      : undefined
                  }
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--prov-surface)",
                    border: "1px solid var(--prov-border)",
                    borderRadius: "var(--prov-radius-md)",
                    fontSize: "var(--prov-size-caption)",
                  }}
                />
                <ReferenceArea
                  x1={formatTimestamp(defect.timestamp_utc)}
                  x2={formatTimestamp(defect.timestamp_utc)}
                  stroke="var(--prov-state-fault)"
                  strokeOpacity={0.9}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="var(--prov-chart-series-1)"
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls={false}
                />
                <Scatter dataKey="flagged" fill="var(--prov-state-fault)" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* -------------------------------------------------- the neighbours */}
      <div className="prov-panel p-4">
        <h4 className="mb-2 text-subhead">Neighbouring stations measuring {defect.parameter}</h4>
        {neighbourIds.length === 0 ? (
          <p className="text-caption text-text-tertiary">
            No other loaded station carries {defect.parameter}, so this reading has nothing to be
            contradicted by. That is a coverage fact, not an endorsement.
          </p>
        ) : (
          <ul className="m-0 list-none space-y-3 p-0">
            {neighbourIds.map((stationId) => (
              <NeighbourSeries
                key={stationId}
                stationId={stationId}
                parameter={defect.parameter}
                start={start}
                end={end}
              />
            ))}
          </ul>
        )}
      </div>

      <ShapAttribution defect={defect} />
      <DeweatherChart stationId={defect.station_id} parameter={defect.parameter} />
      <NotYetComputed
        title="Graph attention over neighbouring stations"
        arrivesIn="the HST-GAT attention overlay lands in phase 6"
      />
      <p className="text-caption text-text-tertiary">
        Adjudication verdict:{" "}
        <span data-testid="evidence-verdict">decided per event on the timeline</span>. This defect
        view is the statistical evidence; whether a rise is a real plume or a sensor fault is
        adjudicated over the wind-conditioned graph, on the{" "}
        <a className="text-interactive underline" href="/timeline">
          event timeline
        </a>
        .
      </p>
    </section>
  );
}

function NeighbourSeries({
  stationId,
  parameter,
  start,
  end,
}: {
  stationId: string;
  parameter: string;
  start: string | null;
  end: string | null;
}) {
  const readings = useReadings({ stationId, parameter, start, end, limit: 200 });
  const values = (readings.data ?? [])
    .map((reading) => reading.value)
    .filter((value): value is number => value !== null);
  const mean = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const unit = readings.data?.[0]?.unit ?? null;

  return (
    <li className="flex items-baseline justify-between gap-3" data-testid="neighbour-series">
      <span className="font-mono text-body">{stationId}</span>
      <span className="prov-numeric text-caption text-text-secondary">
        {values.length} readings · mean {formatMeasurement(mean, unit)}
      </span>
    </li>
  );
}

/**
 * SHAP feature attribution for a flagged reading (phase 5).
 *
 * Fills the slot that was an empty placeholder until the tree models landed. When the
 * model artefacts are present it shows the operator sentence, the fault class, and the
 * top feature contributions as signed bars; when they are absent it says so plainly
 * (graceful degradation, standing rule 6) rather than pretending or spinning forever.
 */
export function ShapAttribution({ defect }: { defect: Defect }) {
  const explain = useExplain(defect.id);

  if (explain.isLoading) {
    return (
      <div className="prov-panel p-4" data-testid="shap-attribution">
        <LoadingState label="Explaining this flag" />
      </div>
    );
  }
  if (explain.error || !explain.data) {
    return (
      <NotYetComputed
        title="Feature attribution (SHAP) for this flag"
        arrivesIn="the explanation could not be loaded"
      />
    );
  }

  const data = explain.data;
  if (data.degraded || data.method !== "model") {
    return (
      <div className="prov-panel p-4" data-testid="shap-attribution">
        <h4 className="mb-1 text-subhead">Feature attribution (SHAP)</h4>
        <p className="text-caption text-text-tertiary" data-testid="shap-degraded">
          {data.method === "rule"
            ? `This flag is decided by a deterministic rule (${data.fault_class ?? "physical"}); there is no model attribution to show.`
            : "No trained model is loaded, so this runs on the statistics layer alone. Train one with `prov models train` to see per-feature SHAP attributions."}
        </p>
      </div>
    );
  }

  return <ShapBars data={data} />;
}

function ShapBars({ data }: { data: Explain }) {
  const top = [...(data.attributions ?? [])]
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 6);
  const maxAbs = Math.max(1e-9, ...top.map((a) => Math.abs(a.value)));

  return (
    <div className="prov-panel p-4" data-testid="shap-attribution">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h4 className="text-subhead">Feature attribution (SHAP)</h4>
        {data.fault_class && (
          <span className="prov-numeric text-caption text-text-tertiary">
            fault class: {data.fault_class}
          </span>
        )}
      </div>
      <p className="mb-3 text-body" data-testid="shap-sentence">
        {data.sentence}
      </p>
      <ul className="m-0 list-none space-y-2 p-0" data-testid="shap-bars">
        {top.map((attr) => {
          const width = `${(Math.abs(attr.value) / maxAbs) * 100}%`;
          const positive = attr.value >= 0;
          return (
            <li key={attr.feature} className="grid grid-cols-[10rem_1fr] items-center gap-2">
              <span className="truncate text-caption text-text-secondary" title={attr.feature}>
                {attr.feature}
                <span className="ml-1 text-micro text-text-tertiary">({attr.provenance})</span>
              </span>
              <span className="relative flex h-4 items-center">
                <span className="absolute inset-y-0 left-1/2 w-px bg-border" aria-hidden />
                <span
                  className="h-3 rounded-sm"
                  style={{
                    width,
                    marginLeft: positive ? "50%" : `calc(50% - ${width})`,
                    background: positive
                      ? "var(--prov-chart-series-1)"
                      : "var(--prov-chart-series-2)",
                  }}
                  title={`${positive ? "raised" : "lowered"} by ${attr.value.toFixed(3)}`}
                />
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-micro text-text-tertiary">
        Bars right of centre raised the weather-predicted value; left lowered it. Attributions plus
        the base value reconstruct the prediction exactly (SHAP additivity).
      </p>
    </div>
  );
}

type DeweatherView = "both" | "raw" | "residual";

/**
 * The before/after deweathering chart (§7.6): raw reading vs weather-predicted vs
 * residual, toggleable. The residual - what the weather does *not* explain - is the
 * series anomaly detection actually sees. Degrades to an honest note when no residuals
 * have been stored (no model trained yet).
 */
export function DeweatherChart({
  stationId,
  parameter,
}: {
  stationId: string;
  parameter: string;
}) {
  const [view, setView] = useState<DeweatherView>("both");
  const deweather = useDeweather(stationId, parameter);

  const chartData = useMemo(
    () =>
      (deweather.data?.series ?? []).map((point) => ({
        label: formatTimestamp(point.timestamp_utc),
        actual: point.actual,
        predicted: point.predicted,
        residual: point.residual,
      })),
    [deweather.data],
  );

  if (deweather.isLoading) {
    return (
      <div className="prov-panel p-4" data-testid="deweather-chart">
        <LoadingState label="Loading the deweathered series" />
      </div>
    );
  }
  if (deweather.error || !deweather.data || deweather.data.degraded || chartData.length === 0) {
    return (
      <NotYetComputed
        title={`Deweathered residual for ${parameter}`}
        arrivesIn="no residuals are stored yet — run `prov models train` then `prov models residuals`"
      />
    );
  }

  return (
    <div className="prov-panel p-4" data-testid="deweather-chart">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-subhead">
          Deweathered {parameter} — raw vs residual
          {deweather.data.model_version && (
            <span className="ml-2 text-micro text-text-tertiary">
              model {deweather.data.model_version}
            </span>
          )}
        </h4>
        <div className="flex gap-1" role="group" aria-label="Deweather view" data-testid="deweather-toggle">
          {(["both", "raw", "residual"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setView(option)}
              aria-pressed={view === option}
              className={`rounded-sm border px-2 py-0.5 text-caption ${
                view === option
                  ? "border-interactive text-interactive"
                  : "border-border text-text-tertiary"
              }`}
            >
              {option === "both" ? "Both" : option === "raw" ? "Raw" : "Residual"}
            </button>
          ))}
        </div>
      </div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--prov-chart-grid)" strokeDasharray="2 4" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
              stroke="var(--prov-chart-grid)"
              minTickGap={64}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
              stroke="var(--prov-chart-grid)"
              width={56}
            />
            <Tooltip
              contentStyle={{
                background: "var(--prov-surface)",
                border: "1px solid var(--prov-border)",
                borderRadius: "var(--prov-radius-md)",
                fontSize: "var(--prov-size-caption)",
              }}
            />
            {view !== "residual" && (
              <Line
                type="monotone"
                dataKey="actual"
                name="raw"
                stroke="var(--prov-chart-series-1)"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
                connectNulls
              />
            )}
            {view !== "raw" && (
              <Line
                type="monotone"
                dataKey="residual"
                name="residual"
                stroke="var(--prov-chart-series-2)"
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-micro text-text-tertiary">
        The residual is actual minus what weather and time alone predict. A flatter residual than raw
        means the weather has been removed; what is left is the signal worth trusting.
      </p>
    </div>
  );
}
