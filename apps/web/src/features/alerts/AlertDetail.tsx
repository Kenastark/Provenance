import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { AlertItem } from "../../api/operations";
import { evidenceFor, sortCodesBySeverity } from "../../api/reason-codes";
import { useEvents, useTrust } from "../../api/queries";
import { FactorBreakdown, type Factor } from "../../components/FactorBreakdown";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { TrustBreakdown } from "../../components/TrustBreakdown";
import { TrustChip, type NonEmpty } from "../../components/TrustChip";
import { parseAdjudication } from "../../lib/adjudication";
import { formatPercent, formatTimestamp } from "../../lib/format";
import { ROLE_LABELS, useRole } from "../../lib/role";
import { AdjudicationDetail } from "../timeline/AdjudicationDetail";
import { VerdictChip } from "../timeline/EventTimeline";
import { SignoffPanel } from "./SignoffPanel";

/**
 * Everything known about one ranked alert, in the order an operator needs it.
 *
 * Risk factors first - severity and exposure said explicitly, the same argument
 * the ranked list makes - then the adjudicator's full case (reused from the Events
 * screen, not rebuilt), then the station's own trust score (reused from the map
 * and quality screens), then the sign-off and dispatch gate.
 */

const RISK_FORMULA = "risk = genuineness × exposure × hazard × (0.5 + 0.5 × confidence)";

export function AlertDetail({ alert }: { alert: AlertItem | null }) {
  const { role } = useRole();
  const stationEvents = useEvents(alert?.station_id);
  const trust = useTrust(alert?.station_id);

  const fullEvent = useMemo(
    () => (stationEvents.data ?? []).find((event) => event.id === alert?.event_id) ?? null,
    [stationEvents.data, alert],
  );
  const adjudication = useMemo(
    () => (fullEvent ? parseAdjudication(fullEvent.evidence) : null),
    [fullEvent],
  );

  if (!alert) {
    return (
      <EmptyState
        title="No alert selected"
        description="Choose a row in the ranked alert list to see its risk factors, its evidence, and the sign-off and dispatch gate."
      />
    );
  }

  const riskFactors: Factor[] = [
    { key: "genuineness", label: "Genuineness", value: alert.risk_factors.genuineness },
    {
      key: "exposure",
      label: "Exposure (rel.)",
      value: alert.risk_factors.exposure,
      hint: "Provisional: min-max normalised across the stations in the current drop, not an absolute figure - not comparable across two different networks without renormalising.",
    },
    { key: "hazard", label: "Hazard", value: alert.risk_factors.hazard },
    { key: "confidence_weight", label: "Confidence weight", value: alert.risk_factors.confidence_weight },
  ];

  const reasonCodes = sortCodesBySeverity(trust.data?.reason_codes ?? []);

  return (
    <div className="flex flex-col gap-5 p-4" data-testid="alert-detail">
      <header>
        <h3 className="text-heading">
          {alert.station_id} · {alert.parameter}
        </h3>
        <p className="mt-1 text-body text-text">{alert.headline}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <VerdictChip verdict={alert.verdict} />
          {fullEvent && <ReasonCodeBadge code={fullEvent.reason_code} variant="code" evidence={evidenceFor(fullEvent)} />}
        </div>
        <p className="mt-2 text-caption text-text-tertiary">
          {formatTimestamp(alert.timestamp_utc)} · severity {alert.severity} · exposure factor{" "}
          {alert.exposure.toFixed(2)} · adjudicator confidence {formatPercent(alert.confidence * 100, 0)}
        </p>
      </header>

      {/* -------------------------------------------------------------- risk */}
      <section aria-labelledby="alert-risk-heading">
        <h4 id="alert-risk-heading" className="mb-2 text-subhead">
          Why this rank
        </h4>
        <FactorBreakdown value={alert.risk} valueLabel="Risk" factors={riskFactors} formula={RISK_FORMULA} />
      </section>

      {/* --------------------------------------------------------- evidence */}
      <section aria-labelledby="alert-evidence-heading">
        <h4 id="alert-evidence-heading" className="mb-2 text-subhead">
          Evidence
        </h4>
        {stationEvents.isLoading && <LoadingState label="Loading evidence" />}
        {stationEvents.error && (
          <ErrorState error={stationEvents.error} what="load this event's evidence" onRetry={stationEvents.refetch} />
        )}
        {!stationEvents.isLoading && !fullEvent && (
          <p className="text-caption text-text-tertiary">
            The audit run this alert came from is no longer the latest one loaded, so its full event
            record is not in the current window.
          </p>
        )}
        {fullEvent &&
          (adjudication ? (
            <AdjudicationDetail event={fullEvent} adjudication={adjudication} />
          ) : (
            <p className="prov-panel p-3 text-caption text-text-tertiary" data-testid="alert-adjudication-pending">
              This event has not been adjudicated yet. Run{" "}
              <code>prov graph adjudicate-db</code> after loading a drop.
            </p>
          ))}
        {fullEvent && (
          <Link
            className="prov-button mt-3 inline-flex"
            to={`/evidence?station=${encodeURIComponent(alert.station_id)}&code=${encodeURIComponent(fullEvent.reason_code)}`}
          >
            View full evidence
          </Link>
        )}
      </section>

      {/* ------------------------------------------------------------ trust */}
      <section aria-labelledby="alert-trust-heading">
        <h4 id="alert-trust-heading" className="mb-2 text-subhead">
          Station trust score
        </h4>
        {trust.isLoading && <LoadingState label="Scoring" />}
        {trust.error && (
          <ErrorState error={trust.error} what={`load the trust score for ${alert.station_id}`} onRetry={trust.refetch} />
        )}
        {trust.data && reasonCodes.length > 0 && (
          <>
            <TrustChip
              trust={trust.data.trust}
              reasonCodes={reasonCodes as unknown as NonEmpty<string>}
              stationId={alert.station_id}
            />
            <TrustBreakdown className="mt-3" components={trust.data.components} />
          </>
        )}
      </section>

      {/* --------------------------------------------------- sign-off & dispatch */}
      <section aria-labelledby="alert-signoff-heading">
        <h4 id="alert-signoff-heading" className="mb-2 text-subhead">
          Sign-off and dispatch
        </h4>
        <p className="mb-3 text-caption text-text-tertiary">
          No code path may publish a public-facing alert without a recorded human sign-off. This is
          enforced server-side; the form below is how you produce one.
        </p>
        <SignoffPanel eventId={alert.event_id} defaultOperator={ROLE_LABELS[role]} />
      </section>
    </div>
  );
}
