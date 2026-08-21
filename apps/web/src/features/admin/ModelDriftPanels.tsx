import type { DriftSeries, ModelDriftReport } from "../../api/operations";
import { DataTable, type Column } from "../../components/DataTable";
import { NotYetComputed } from "../../components/States";
import { Sparkline } from "../../components/Sparkline";

/**
 * The model plane of the two-plane monitor - deliberately separate from
 * `/metrics` (the infra plane, `InfraHealthPanel`). "Are the models and the data
 * drifting" is a different question from "is the service up", and the phase-7
 * prompt for this router says so directly in its own docstring.
 *
 * A `DriftSeries` with one point or fewer is exactly the pre-training state - the
 * gap this component exists to handle honestly: it says "no history yet" in words
 * rather than drawing a one-point chart, which would visually claim a trend that
 * is not there.
 */

const DIRECTION_LABEL: Record<DriftSeries["direction"], string> = {
  up: "↑ rising",
  down: "↓ falling",
  flat: "→ flat",
  unknown: "no direction yet",
};

/**
 * `unit` names what a series' numbers already are - never a hint to transform
 * them. `ops/drift.py::defect_rate_drift_by_station` computes "percent" values
 * that are already ×100 (41.51, not 0.4151); `r2_drift`/`conformal_coverage_drift`
 * report the raw statistic under "r2"/"fraction". Re-deriving a percentage from a
 * value the backend already converted is exactly the kind of silent unit mismatch
 * that reads as a real number and is wrong - this formats whatever the backend
 * sent, once, and appends the unit it actually named.
 */
function formatDriftValue(value: number | null, unit: string): string {
  if (value === null || Number.isNaN(value)) return "—";
  const digits = Math.abs(value) >= 10 ? 1 : 3;
  return unit === "percent" ? `${value.toFixed(digits)}%` : `${value.toFixed(digits)} ${unit}`;
}

export function DriftSeriesPanel({ series }: { series: DriftSeries }) {
  const hasHistory = series.points.length > 1;
  return (
    <div className="prov-panel p-4" data-testid="drift-series-panel">
      <h4 className="text-subhead">{series.name}</h4>
      {hasHistory ? (
        <>
          <Sparkline
            label={series.name}
            unit={series.unit}
            points={series.points.map((point) => ({ t: point.at, value: point.value }))}
            width={280}
            height={48}
            fluid
          />
          <p className="mt-2 text-caption text-text-secondary">
            baseline {formatDriftValue(series.baseline, series.unit)} → latest{" "}
            {formatDriftValue(series.latest, series.unit)} · {DIRECTION_LABEL[series.direction]}
          </p>
        </>
      ) : (
        <p className="mt-2 text-caption text-text-tertiary" data-testid="drift-no-history">
          No history yet — {series.note}
        </p>
      )}
    </div>
  );
}

interface StationDriftRow {
  stationId: string;
  series: DriftSeries;
}

function StationDriftTable({ series }: { series: Record<string, DriftSeries> }) {
  const rows: StationDriftRow[] = Object.entries(series).map(([stationId, s]) => ({
    stationId,
    series: s,
  }));

  const columns: Column<StationDriftRow>[] = [
    {
      key: "station",
      header: "Station",
      isRowHeader: true,
      sortValue: (row) => row.stationId,
      render: (row) => <span className="font-mono">{row.stationId}</span>,
    },
    {
      key: "latest",
      header: "Latest defect rate",
      align: "right",
      sortValue: (row) => row.series.latest ?? -1,
      render: (row) => formatDriftValue(row.series.latest, row.series.unit),
    },
    {
      key: "baseline",
      header: "Baseline",
      align: "right",
      sortValue: (row) => row.series.baseline ?? -1,
      render: (row) => formatDriftValue(row.series.baseline, row.series.unit),
    },
    {
      key: "history",
      header: "History",
      render: (row) =>
        row.series.points.length > 1 ? (
          <Sparkline
            label={`Defect rate at ${row.stationId}`}
            points={row.series.points.map((point) => ({ t: point.at, value: point.value }))}
            width={100}
            height={24}
          />
        ) : (
          <span className="text-caption text-text-tertiary">no history yet</span>
        ),
    },
  ];

  return (
    <DataTable
      rows={rows}
      columns={columns}
      rowKey={(row) => row.stationId}
      caption="Defect-rate drift by station"
      initialSort={{ key: "station", direction: "asc" }}
      maxBodyHeight={320}
      emptyMessage="No station has a stored audit run yet."
    />
  );
}

export function ModelDriftPanels({ report }: { report: ModelDriftReport }) {
  const stationCount = Object.keys(report.defect_rate_by_station).length;
  return (
    <div className="flex flex-col gap-4" data-testid="model-drift-panels">
      <p className="text-caption text-text-tertiary">{report.note}</p>

      <div>
        <h4 className="mb-2 text-subhead">Defect rate by station</h4>
        {stationCount === 0 ? (
          <p className="text-caption text-text-tertiary">No stored audit run to compare against yet.</p>
        ) : (
          <StationDriftTable series={report.defect_rate_by_station} />
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <DriftSeriesPanel series={report.deweather_r2} />
        <DriftSeriesPanel series={report.conformal_coverage} />
      </div>

      <div>
        <h4 className="mb-2 text-subhead">Fault classifier confusion</h4>
        {report.fault_confusion.available ? (
          <pre className="prov-panel overflow-auto p-3 text-caption" data-testid="fault-confusion-available">
            {JSON.stringify(report.fault_confusion, null, 2)}
          </pre>
        ) : (
          <NotYetComputed
            title="Fault classifier confusion matrix"
            arrivesIn={report.fault_confusion.note ?? "train the fault classifier"}
          />
        )}
      </div>
    </div>
  );
}
