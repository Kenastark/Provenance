import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Defect, QualityStation, Station } from "../../api/client";
import { useDefects, useQualitySummary, useStations } from "../../api/queries";
import { DataTable, type Column } from "../../components/DataTable";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { StateGlyph } from "../../components/StateGlyph";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatCount, formatDate, formatPercent, formatRelative, formatTrust } from "../../lib/format";
import { trustState, trustStateLabel } from "../../lib/trust";
import { useWindowState } from "../../lib/windowContext";
import { StationDetailPanel } from "../station/StationDetailPanel";

/**
 * The Data Quality Monitor: one dense row per station.
 *
 * Two of the columns are computed here rather than served, because the API has no
 * field for either and inventing one would be worse than deriving it:
 *
 * * **Uptime** is 1 - (absent hours / expected hours), and absent hours are exactly
 *   what R01 counts. Missingness in this corpus appears as absent rows rather than
 *   nulls, so the audit's own R01 ledger is the honest source.
 * * **Last calibration epoch** is the newest R15 discontinuity the audit detected.
 *   Where no discontinuity was found the cell says so; it does not say "unknown" as
 *   though a date existed somewhere and we failed to fetch it.
 *
 * Both derivations are stated in the column help text, on screen, next to the
 * number - the same discipline the audit report applies to the defect rate.
 */

interface QualityRow {
  station: QualityStation;
  meta: Station | undefined;
  absentHours: number;
  expectedHours: number | null;
  uptimePct: number | null;
  lastCalibration: string | null;
}

function buildRows(
  quality: readonly QualityStation[],
  stations: readonly Station[],
  absences: readonly Defect[],
  calibrations: readonly Defect[],
  windowHours: number | null,
): QualityRow[] {
  const stationById = new Map(stations.map((s) => [s.station_id, s]));

  const absentByStation = new Map<string, number>();
  for (const defect of absences) {
    absentByStation.set(defect.station_id, (absentByStation.get(defect.station_id) ?? 0) + 1);
  }

  const calibrationByStation = new Map<string, string>();
  for (const defect of calibrations) {
    const current = calibrationByStation.get(defect.station_id);
    if (!current || defect.timestamp_utc > current) {
      calibrationByStation.set(defect.station_id, defect.timestamp_utc);
    }
  }

  return quality.map((station) => {
    const absentHours = absentByStation.get(station.station_id) ?? 0;
    // Expected cells over the window: one per parameter per hour. Without a bounded
    // window (full corpus) there is no denominator to divide by here, and the
    // column honestly shows nothing rather than a number derived from nothing.
    const expectedHours =
      windowHours !== null && station.n_parameters > 0 ? windowHours * station.n_parameters : null;
    return {
      station,
      meta: stationById.get(station.station_id),
      absentHours,
      expectedHours,
      uptimePct:
        expectedHours && expectedHours > 0
          ? Math.max(0, 100 * (1 - absentHours / expectedHours))
          : null,
      lastCalibration: calibrationByStation.get(station.station_id) ?? null,
    };
  });
}

export function QualityMonitor() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStationId = searchParams.get("station");
  const { resolved, timeWindow } = useWindowState();
  const [filter, setFilter] = useState("");
  const [stateFilter, setStateFilter] = useState<"all" | "verified" | "degraded" | "fault" | "unknown">("all");

  const quality = useQualitySummary();
  const stations = useStations();
  const absences = useDefects({ code: "R01", start: resolved.start, end: resolved.end });
  const calibrations = useDefects({ code: "R15", start: resolved.start, end: resolved.end });

  const windowHours = useMemo(() => {
    if (!resolved.start || !resolved.end) return null;
    return (new Date(resolved.end).getTime() - new Date(resolved.start).getTime()) / 3600_000;
  }, [resolved]);

  const rows = useMemo(
    () =>
      buildRows(
        quality.data?.stations ?? [],
        stations.data ?? [],
        absences.data?.items ?? [],
        calibrations.data?.items ?? [],
        windowHours,
      ),
    [quality.data, stations.data, absences.data, calibrations.data, windowHours],
  );

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return rows.filter((row) => {
      if (stateFilter !== "all" && trustState(row.station.trust) !== stateFilter) return false;
      if (!needle) return true;
      return (
        row.station.station_id.toLowerCase().includes(needle) ||
        (row.meta?.name ?? "").toLowerCase().includes(needle) ||
        (row.station.zone_type ?? "").toLowerCase().includes(needle) ||
        (row.station.reason_codes ?? []).some((code) => code.toLowerCase().includes(needle))
      );
    });
  }, [rows, filter, stateFilter]);

  const columns: Column<QualityRow>[] = useMemo(
    () => [
      {
        key: "station",
        header: "Station",
        isRowHeader: true,
        sortValue: (row) => row.station.station_id,
        render: (row) => (
          <span className="flex items-center gap-2">
            <span className={`prov-state-${trustState(row.station.trust)}`}>
              <StateGlyph state={trustState(row.station.trust)} size={10} decorative />
            </span>
            <span className="font-mono">{row.station.station_id}</span>
            {row.meta?.name && (
              <span className="truncate text-text-tertiary">{row.meta.name}</span>
            )}
          </span>
        ),
      },
      {
        key: "state",
        header: "State",
        sortValue: (row) => trustStateLabel(trustState(row.station.trust)),
        render: (row) => trustStateLabel(trustState(row.station.trust)),
      },
      {
        key: "trust",
        header: "Trust",
        align: "right",
        sortValue: (row) => row.station.trust,
        render: (row) => formatTrust(row.station.trust),
      },
      {
        key: "health",
        header: "Health",
        align: "right",
        sortValue: (row) => row.station.health,
        render: (row) => formatTrust(row.station.health),
      },
      {
        key: "uptime",
        header: "Uptime",
        align: "right",
        sortValue: (row) => row.uptimePct,
        render: (row) =>
          row.uptimePct === null ? (
            <span className="text-text-tertiary">—</span>
          ) : (
            <span title={`${row.absentHours} absent of ${row.expectedHours} expected cells`}>
              {formatPercent(row.uptimePct)}
            </span>
          ),
      },
      {
        key: "calibration",
        header: "Last calibration",
        sortValue: (row) => row.lastCalibration,
        render: (row) =>
          row.lastCalibration ? (
            formatDate(row.lastCalibration)
          ) : (
            <span className="text-text-tertiary">none detected</span>
          ),
      },
      {
        key: "flags",
        header: "Flags",
        align: "right",
        sortValue: (row) => row.station.flag_count,
        render: (row) => formatCount(row.station.flag_count),
      },
      {
        key: "codes",
        header: "Reason codes",
        render: (row) => (
          <span className="flex flex-wrap gap-1">
            {(row.station.reason_codes ?? []).slice(0, 4).map((code) => (
              <ReasonCodeBadge key={code} code={code} variant="code" />
            ))}
          </span>
        ),
      },
      {
        key: "last",
        header: "Last reading",
        sortValue: (row) => row.station.last_reading_at,
        render: (row) => formatRelative(row.station.last_reading_at),
      },
    ],
    [],
  );

  if (quality.isLoading || stations.isLoading) return <LoadingState label="Loading quality summary" />;
  if (quality.error) {
    return (
      <ErrorState
        error={quality.error}
        what="load the data quality summary"
        onRetry={quality.refetch}
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col lg:flex-row">
      <section className="flex min-w-0 flex-1 flex-col gap-3 p-4" aria-label="Data quality monitor">
        <header className="flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <h2 className="text-heading">Data quality monitor</h2>
            <p className="text-caption text-text-tertiary">
              {filtered.length} of {rows.length} stations · uptime is 1 − (R01 absent cells ÷
              expected cells) over the {resolved.label.toLowerCase()} window
              {timeWindow === "corpus" && ", which has no bounded denominator — switch to 24h or 7d for uptime"}
              .
            </p>
          </div>
          <label className="flex items-center gap-2 text-caption text-text-tertiary">
            <span>Filter</span>
            <input
              className="prov-input"
              type="search"
              value={filter}
              placeholder="station, zone, code"
              onChange={(event) => setFilter(event.target.value)}
              data-testid="quality-filter"
            />
          </label>
          <label className="flex items-center gap-2 text-caption text-text-tertiary">
            <span>State</span>
            <select
              className="prov-input"
              value={stateFilter}
              onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)}
              data-testid="quality-state-filter"
            >
              <option value="all">All</option>
              <option value="verified">Verified</option>
              <option value="degraded">Anomaly</option>
              <option value="fault">Fault</option>
              <option value="unknown">Not scored</option>
            </select>
          </label>
        </header>

        {rows.length === 0 ? (
          <div className="prov-panel">
            <EmptyState
              title="No stations in the latest audit run"
              description="Load a data drop and run the audit (`make demo` does both) to populate the monitor."
            />
          </div>
        ) : (
          <div className="prov-panel min-h-0 min-w-0 flex-1 overflow-hidden">
            <DataTable
              rows={filtered}
              columns={columns}
              rowKey={(row) => row.station.station_id}
              caption="Stations by trust, health, uptime and flag count"
              initialSort={{ key: "trust", direction: "asc" }}
              selectedKey={selectedStationId}
              onRowActivate={(row) =>
                setSearchParams((previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("station", row.station.station_id);
                  return next;
                })
              }
              maxBodyHeight={640}
              emptyMessage="No station matches this filter."
            />
          </div>
        )}
      </section>

      <StationDetailPanel
        stationId={selectedStationId}
        station={stations.data?.find((s) => s.station_id === selectedStationId) ?? null}
        qualityRow={
          quality.data?.stations.find((s) => s.station_id === selectedStationId) ?? null
        }
        onClose={() =>
          setSearchParams((previous) => {
            const next = new URLSearchParams(previous);
            next.delete("station");
            return next;
          })
        }
      />
    </div>
  );
}

export { buildRows as buildQualityRows };
