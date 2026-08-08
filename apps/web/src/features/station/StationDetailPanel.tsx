import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { QualityStation, Station, TrustComponent } from "../../api/client";
import { evidenceFor, sortCodesBySeverity } from "../../api/reason-codes";
import { useDefects, useReadings, useTrust, useTrustSeries } from "../../api/queries";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { Sparkline } from "../../components/Sparkline";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { TrustBreakdown } from "../../components/TrustBreakdown";
import { TrustChip, type NonEmpty } from "../../components/TrustChip";
import { formatCount, formatRelative, formatTimestamp } from "../../lib/format";
import { queueAction, queuedActionsFor, QUEUE_DISCLOSURE } from "../../lib/queue";
import { trustBandDescription, trustState } from "../../lib/trust";
import { useWindowState } from "../../lib/windowContext";

/**
 * Everything known about one station, in the order an operator needs it.
 *
 * Score first, then *why* - the component breakdown and the reason codes as
 * sentences - then the series the claim rests on, then the coverage facts, then the
 * actions. A trust score at the top with no explanation under it would make this a
 * prettier version of the dashboard Provenance exists to second-guess.
 */

/** Which component's `detail` explains which trust code, for partial sentences. */
const CODE_TO_COMPONENT: Record<string, string> = {
  T01: "HealthConf",
  T02: "ImputationCertainty",
  T03: "CrossSensorConsistency",
  T05: "CrossSensorConsistency",
  T04: "PhysicalPlausibility",
};

function detailFor(code: string, components: readonly TrustComponent[]): string | null {
  const name = CODE_TO_COMPONENT[code];
  if (!name) return null;
  return components.find((component) => component.name === name)?.detail ?? null;
}

export interface StationDetailPanelProps {
  stationId: string | null;
  station: Station | null;
  qualityRow: QualityStation | null;
  onClose: () => void;
}

export function StationDetailPanel({
  stationId,
  station,
  qualityRow,
  onClose,
}: StationDetailPanelProps) {
  if (!stationId) {
    return (
      <aside
        className="hidden w-full min-w-0 shrink-0 border-l border-border bg-bg-raised lg:block"
        style={{ maxWidth: "var(--prov-drawer-width)" }}
        aria-label="Station detail"
      >
        <EmptyState
          title="No station selected"
          description="Choose a marker on the map, or a row in the data quality monitor, to see its trust score, the reasons behind it, and the series it rests on."
        />
      </aside>
    );
  }

  return (
    <aside
      // Stacked and full width on a narrow screen; a fixed rail beside the content
      // from `lg` up. `min-w-0` so a long station name cannot widen the page.
      className="flex w-full min-w-0 shrink-0 flex-col overflow-y-auto border-t border-border bg-bg-raised lg:max-w-[var(--prov-drawer-width)] lg:border-l lg:border-t-0"
      aria-label={`Station detail for ${stationId}`}
      data-testid="station-detail-panel"
    >
      <StationDetailBody
        stationId={stationId}
        station={station}
        qualityRow={qualityRow}
        onClose={onClose}
      />
    </aside>
  );
}

function StationDetailBody({
  stationId,
  station,
  qualityRow,
  onClose,
}: {
  stationId: string;
  station: Station | null;
  qualityRow: QualityStation | null;
  onClose: () => void;
}) {
  const { resolved } = useWindowState();
  const trust = useTrust(stationId);
  const series = useTrustSeries(stationId);
  // R18 is the authoritative structural-absence signal. It is a coverage fact, and
  // it never counts toward the defect rate.
  const coverageFacts = useDefects({ station: stationId, code: "R18" });
  const [queued, setQueued] = useState(() => queuedActionsFor(stationId));
  const [showAllParameters, setShowAllParameters] = useState(false);

  const score = trust.data;
  const reasonCodes = useMemo(
    () => sortCodesBySeverity(score?.reason_codes ?? qualityRow?.reason_codes ?? []),
    [score, qualityRow],
  );
  const components = score?.components ?? qualityRow?.components ?? [];

  const parameters = useMemo(() => {
    const coverage = station?.coverage ?? {};
    return Object.keys(coverage).sort();
  }, [station]);
  const visibleParameters = showAllParameters ? parameters : parameters.slice(0, 6);

  const act = (kind: "acknowledge" | "dispatch") => {
    queueAction({ kind, stationId, reasonCodes });
    setQueued(queuedActionsFor(stationId));
  };

  return (
    <div className="flex flex-col gap-5 p-4">
      <header className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-heading">{stationId}</h2>
          {station?.name && <p className="text-caption text-text-secondary">{station.name}</p>}
          <p className="text-caption text-text-tertiary">
            {station?.zone_type ? `${station.zone_type} zone · ` : ""}
            {qualityRow?.last_reading_at
              ? `last reading ${formatRelative(qualityRow.last_reading_at)}`
              : "no readings"}
          </p>
        </div>
        <button type="button" className="prov-button" onClick={onClose} aria-label="Close station detail">
          Close
        </button>
      </header>

      {/* ------------------------------------------------------------ trust */}
      <section aria-labelledby="station-trust-heading">
        <h3 id="station-trust-heading" className="mb-2 text-subhead">
          Trust score
        </h3>
        {trust.isLoading && <LoadingState label="Scoring" />}
        {trust.error && (
          <ErrorState
            error={trust.error}
            what={`load the trust score for ${stationId}`}
            onRetry={trust.refetch}
          />
        )}
        {score && reasonCodes.length > 0 && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <TrustChip
                trust={score.trust}
                reasonCodes={reasonCodes as unknown as NonEmpty<string>}
                stationId={stationId}
              />
              {score.degraded && (
                <span className="text-caption prov-state-degraded" data-testid="degraded-badge">
                  Degraded mode — statistics layer only
                </span>
              )}
            </div>
            <p className="mt-2 text-caption text-text-tertiary">
              {trustBandDescription(trustState(score.trust))} Scored at{" "}
              {formatTimestamp(score.timestamp_utc)}.
            </p>

            <h4 className="mb-1 mt-4 text-caption uppercase tracking-wide text-text-tertiary">
              Why
            </h4>
            <ul className="m-0 list-none space-y-2 p-0" data-testid="station-reason-codes">
              {reasonCodes.map((code) => (
                <li key={code}>
                  <ReasonCodeBadge
                    code={code}
                    evidence={{ n_defects: qualityRow?.flag_count }}
                    detail={detailFor(code, components)}
                  />
                </li>
              ))}
            </ul>

            <h4 className="mb-1 mt-4 text-caption uppercase tracking-wide text-text-tertiary">
              Components
            </h4>
            <TrustBreakdown components={components} />

            {(score.notes ?? []).length > 0 && (
              <ul className="mt-3 list-none space-y-1 p-0 text-caption text-text-tertiary">
                {(score.notes ?? []).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {/* ------------------------------------------------- trust trajectory */}
      <section aria-labelledby="station-trajectory-heading">
        <h3 id="station-trajectory-heading" className="mb-2 text-subhead">
          Trust trajectory
        </h3>
        {series.isLoading && <LoadingState label="Loading history" />}
        {series.data && series.data.length > 0 ? (
          <Sparkline
            label={`Trust at ${stationId}`}
            width={320}
            height={44}
            points={series.data.map((point) => ({
              t: point.timestamp_utc,
              value: point.trust,
              flagged: trustState(point.trust) === "fault",
            }))}
          />
        ) : (
          !series.isLoading && (
            <p className="text-caption text-text-tertiary">
              Only one score exists for this station so far.
            </p>
          )
        )}
      </section>

      {/* ------------------------------------------------------- parameters */}
      <section aria-labelledby="station-parameters-heading">
        <h3 id="station-parameters-heading" className="mb-2 text-subhead">
          Parameters
        </h3>
        {parameters.length === 0 ? (
          <p className="text-caption text-text-tertiary">
            No parameter coverage recorded for this station.
          </p>
        ) : (
          <ul className="m-0 list-none space-y-3 p-0">
            {visibleParameters.map((parameter) => (
              <ParameterSparkline
                key={parameter}
                stationId={stationId}
                parameter={parameter}
                count={station?.coverage?.[parameter] ?? 0}
                start={resolved.start}
                end={resolved.end}
              />
            ))}
          </ul>
        )}
        {parameters.length > visibleParameters.length && (
          <button
            type="button"
            className="prov-button mt-3"
            onClick={() => setShowAllParameters(true)}
          >
            Show all {parameters.length} parameters
          </button>
        )}
      </section>

      {/* --------------------------------------------------------- coverage */}
      {coverageFacts.data && coverageFacts.data.length > 0 && (
        <section aria-labelledby="station-coverage-heading">
          <h3 id="station-coverage-heading" className="mb-2 text-subhead">
            Coverage
          </h3>
          <ul className="m-0 list-none space-y-2 p-0" data-testid="station-coverage-facts">
            {coverageFacts.data.map((fact) => (
              <li key={`${fact.reason_code}-${fact.parameter}`}>
                <ReasonCodeBadge code={fact.reason_code} evidence={evidenceFor(fact)} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ---------------------------------------------------------- actions */}
      <section aria-labelledby="station-actions-heading">
        <h3 id="station-actions-heading" className="mb-2 text-subhead">
          Actions
        </h3>
        <div className="flex flex-wrap gap-2">
          <Link
            className="prov-button prov-button--primary"
            to={`/evidence?station=${encodeURIComponent(stationId)}`}
          >
            View evidence
          </Link>
          <button type="button" className="prov-button" onClick={() => act("acknowledge")}>
            Acknowledge
          </button>
          <button type="button" className="prov-button" onClick={() => act("dispatch")}>
            Dispatch
          </button>
        </div>
        <p className="mt-2 text-caption text-text-tertiary">{QUEUE_DISCLOSURE}</p>
        {queued.length > 0 && (
          <ul
            className="mt-3 list-none space-y-1 p-0 text-caption text-text-secondary"
            data-testid="queued-actions"
          >
            {queued.map((action) => (
              <li key={action.id}>
                {action.kind === "acknowledge" ? "Acknowledged" : "Dispatch queued"} ·{" "}
                {formatTimestamp(action.queuedAt)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ParameterSparkline({
  stationId,
  parameter,
  count,
  start,
  end,
}: {
  stationId: string;
  parameter: string;
  count: number;
  start: string | null;
  end: string | null;
}) {
  const readings = useReadings({ stationId, parameter, start, end, limit: 200 });
  const points = (readings.data ?? []).map((reading) => ({
    t: reading.timestamp_utc,
    value: reading.value,
    flagged: (reading.reason_codes?.length ?? 0) > 0,
  }));
  const unit = readings.data?.[0]?.unit ?? null;

  return (
    <li className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="truncate text-body">{parameter}</p>
        <p className="prov-numeric text-caption text-text-tertiary">
          {formatCount(count)} readings
          {unit ? ` · ${unit}` : ""}
        </p>
      </div>
      {readings.isLoading ? (
        <span className="text-caption text-text-tertiary">…</span>
      ) : (
        <Sparkline label={`${parameter} at ${stationId}`} unit={unit} points={points} />
      )}
    </li>
  );
}
