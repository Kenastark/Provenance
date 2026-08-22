import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
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
  useAttentionOverlay,
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
import { haversineKm } from "../map/windEdges";

/**
 * Why a particular reading is wrong.
 *
 * The reason-code sentence, the detector's own evidence numbers, the raw series
 * around the flagged point with the flagged region marked, and the neighbouring
 * stations that contradict it. This screen is the argument; everything else in the
 * dashboard is navigation to it.
 *
 * SHAP and graph attention each degrade to an explicit "not yet computed" slot when
 * their artefact is absent, rather than being hidden — so the finished shape is
 * visible even before a model has been trained.
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
      <header className="sticky top-0 z-10 -mx-4 -mt-4 flex flex-wrap items-end gap-3 border-b border-border bg-bg px-4 pb-3 pt-4">
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

  // The neighbours this reading contradicts: the nearest other stations that carry
  // the same parameter, ranked by real distance when the flagged station has
  // coordinates to rank from. Which of them are *physically connected* (wind-aware)
  // is a phase-4 question, answered by the wind-conditioned graph; until then the
  // honest claim is "the closest stations measuring the same thing at the same
  // time", not an arbitrary 3 - so this sorts by haversine distance rather than
  // taking whatever order the station list happens to arrive in.
  const targetStation = (stations.data ?? []).find((s) => s.station_id === defect.station_id);
  const rankedByDistance = targetStation?.lat != null && targetStation?.lon != null;
  const neighbours = useMemo(() => {
    const candidates = (stations.data ?? []).filter(
      (station) =>
        station.station_id !== defect.station_id &&
        Object.prototype.hasOwnProperty.call(station.coverage ?? {}, defect.parameter),
    );
    if (!rankedByDistance || !targetStation) {
      return candidates
        .slice(0, 3)
        .map((station) => ({ stationId: station.station_id, distanceKm: null as number | null }));
    }
    const lat = targetStation.lat as number;
    const lon = targetStation.lon as number;
    return candidates
      .map((station) => ({
        stationId: station.station_id,
        distanceKm:
          station.lat != null && station.lon != null
            ? haversineKm(lat, lon, station.lat, station.lon)
            : null,
      }))
      .sort((a, b) => (a.distanceKm ?? Infinity) - (b.distanceKm ?? Infinity))
      .slice(0, 3);
  }, [stations.data, defect, rankedByDistance, targetStation]);

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
          <dl
            className="grid grid-cols-[max-content_1fr] gap-x-3 text-caption"
            data-testid="evidence-numbers"
          >
            {Object.entries(defect.evidence).map(([key, value], index, entries) => {
              const divider = index < entries.length - 1 ? "border-b border-border" : "";
              return (
                <div key={key} className="contents">
                  <dt className={`py-1.5 text-text-tertiary ${divider}`}>{key}</dt>
                  <dd className={`prov-numeric m-0 py-1.5 font-mono text-text ${divider}`}>
                    {typeof value === "number" ? formatMeasurement(value) : String(value)}
                  </dd>
                </div>
              );
            })}
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
        <h4 className="mb-2 text-subhead">
          {rankedByDistance ? "Nearest stations" : "Neighbouring stations"} measuring{" "}
          {defect.parameter}
        </h4>
        {neighbours.length === 0 ? (
          <p className="text-caption text-text-tertiary">
            No other loaded station carries {defect.parameter}, so this reading has nothing to be
            contradicted by. That is a coverage fact, not an endorsement.
          </p>
        ) : (
          <ul className="m-0 list-none space-y-3 p-0">
            {neighbours.map((neighbour) => (
              <NeighbourSeries
                key={neighbour.stationId}
                stationId={neighbour.stationId}
                parameter={defect.parameter}
                start={start}
                end={end}
                distanceKm={neighbour.distanceKm}
              />
            ))}
          </ul>
        )}
      </div>

      <ShapAttribution defect={defect} />
      <DeweatherChart stationId={defect.station_id} parameter={defect.parameter} />
      <GraphAttention defect={defect} />
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
  distanceKm,
}: {
  stationId: string;
  parameter: string;
  start: string | null;
  end: string | null;
  distanceKm: number | null;
}) {
  const readings = useReadings({ stationId, parameter, start, end, limit: 200 });
  const values = (readings.data ?? [])
    .map((reading) => reading.value)
    .filter((value): value is number => value !== null);
  const mean = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const unit = readings.data?.[0]?.unit ?? null;

  return (
    <li className="flex items-baseline justify-between gap-3" data-testid="neighbour-series">
      <span className="font-mono text-body">
        {stationId}
        {distanceKm != null && (
          <span className="ml-2 text-micro text-text-tertiary">{distanceKm.toFixed(1)} km</span>
        )}
      </span>
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
            ? (data.notes?.[0] ??
              `This flag is decided by a deterministic rule${data.fault_class ? ` (${data.fault_class})` : ""}; there is no model attribution to show.`)
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
          // Drawn from a centreline in both directions, so each side only ever
          // owns half the track - capping at 50% (not 100%) keeps the largest bar
          // from overrunning the card's right edge.
          const width = `${(Math.abs(attr.value) / maxAbs) * 50}%`;
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

/**
 * The HST-GAT's learned attention over this reading's station (phase 6, §8).
 *
 * `/v1/graph/attention` is the same endpoint the Network Map's "Learned attention"
 * layer reads; this shows the subset of edges that touch the flagged station,
 * relation by relation. Degrades to the backend's own reason (no trained artefact,
 * or its target parameter absent from the loaded drop — standing rule 6) rather than
 * a hardcoded placeholder, and never claims an accuracy figure for what is a
 * read-out of attention weights (standing rule 4).
 */
export function GraphAttention({ defect }: { defect: Defect }) {
  const overlay = useAttentionOverlay();

  if (overlay.isLoading) {
    return (
      <div className="prov-panel p-4" data-testid="graph-attention">
        <LoadingState label="Loading the attention overlay" />
      </div>
    );
  }
  if (overlay.error || !overlay.data) {
    return (
      <NotYetComputed
        title="Graph attention over neighbouring stations"
        arrivesIn="the attention overlay could not be loaded"
      />
    );
  }

  const data = overlay.data;
  if (!data.available) {
    return (
      <NotYetComputed
        title="Graph attention over neighbouring stations"
        arrivesIn={data.reason ?? "the HST-GAT has not been trained"}
      />
    );
  }

  // The network only ever trains one HST-GAT at a time (`models.yaml`'s
  // `hstgat.target_parameter`), so this overlay can easily be showing a different
  // pollutant's propagation structure than the one the operator is actually looking
  // at - real, but easy to miss glancing at the small "target X" caption alone. Flagged
  // in amber (the brand's own "ambiguity" colour) rather than left to the caption.
  const parameterMismatch = Boolean(
    data.target_parameter && data.target_parameter !== defect.parameter,
  );
  const mismatchNote = parameterMismatch && (
    <p
      className="mb-2 text-caption prov-state-degraded"
      data-testid="attention-parameter-mismatch"
    >
      This overlay is trained to reconstruct {data.target_parameter}, not{" "}
      {defect.parameter} - read it as {data.target_parameter} network structure, not
      evidence about this {defect.parameter} reading.
    </p>
  );

  const allEdges = Object.entries(data.relations ?? {})
    .flatMap(([relation, relationEdges]) =>
      relationEdges
        .filter((edge) => edge.src === defect.station_id || edge.dst === defect.station_id)
        .map((edge) => ({ ...edge, relation })),
    )
    .sort((a, b) => b.attention - a.attention);

  if (allEdges.length === 0) {
    return (
      <div className="prov-panel p-4" data-testid="graph-attention">
        <h4 className="mb-1 text-subhead">Graph attention over neighbouring stations</h4>
        {mismatchNote}
        <p className="text-caption text-text-tertiary" data-testid="graph-attention-empty">
          The trained HST-GAT (target {data.target_parameter}) carries no attention edges
          touching {defect.station_id}. That is a graph-topology fact, not a missing
          computation.
        </p>
      </div>
    );
  }

  // The full edge set can run into the dozens across both relation types; capped to
  // the strongest few (mirroring ShapBars' own top-6 cap) so the card stays scannable
  // rather than an unbroken wall of near-identical bars - the omission is stated
  // rather than silent, the same "truncated" honesty the defect table uses.
  const EDGE_CAP = 8;
  const edges = allEdges.slice(0, EDGE_CAP);
  const maxAttention = Math.max(1e-9, ...edges.map((edge) => edge.attention));

  return (
    <div className="prov-panel p-4" data-testid="graph-attention">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h4 className="text-subhead">Graph attention over neighbouring stations</h4>
        <span
          className={`prov-numeric text-caption ${parameterMismatch ? "prov-state-degraded" : "text-text-tertiary"}`}
        >
          target {data.target_parameter}
          {data.at && <> · {formatTimestamp(data.at)}</>}
        </span>
      </div>
      {mismatchNote}
      <ul className="m-0 list-none space-y-2 p-0" data-testid="attention-edges">
        {edges.map((edge) => {
          const outgoing = edge.src === defect.station_id;
          const neighbour = outgoing ? edge.dst : edge.src;
          const width = `${(edge.attention / maxAttention) * 100}%`;
          return (
            <li
              key={`${edge.relation}-${edge.src}-${edge.dst}`}
              className="grid grid-cols-[14rem_1fr_3.5rem] items-center gap-2"
            >
              <span className="truncate text-caption text-text-secondary" title={edge.relation}>
                {outgoing ? "→" : "←"} <span className="font-mono">{neighbour}</span>
                <span className="ml-1 text-micro text-text-tertiary">({edge.relation})</span>
              </span>
              <span className="relative flex h-4 items-center">
                <span
                  className="h-3 rounded-sm"
                  style={{ width, background: "var(--prov-chart-series-1)" }}
                />
              </span>
              <span className="prov-numeric text-right text-micro text-text-tertiary">
                {edge.attention.toFixed(3)}
              </span>
            </li>
          );
        })}
      </ul>
      {allEdges.length > EDGE_CAP && (
        <p className="mt-2 text-micro text-text-tertiary" data-testid="attention-edges-truncated">
          Showing the strongest {EDGE_CAP} of {allEdges.length} edges touching{" "}
          {defect.station_id}.
        </p>
      )}
      <p className="mt-2 text-micro text-text-tertiary">
        Softmax attention weight over {defect.station_id}'s edges of each relation — a
        read-out of what the model attended to, never an accuracy claim.
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
            <Legend wrapperStyle={{ fontSize: "var(--prov-size-caption)" }} />
            {view !== "residual" && (
              <Line
                type="monotone"
                dataKey="actual"
                name="Raw"
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
                name="Residual"
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
