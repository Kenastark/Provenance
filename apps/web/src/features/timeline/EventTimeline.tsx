import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ProvEvent } from "../../api/client";
import { evidenceFor, reasonCode, severityTone } from "../../api/reason-codes";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { useEvents } from "../../api/queries";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { parseAdjudication } from "../../lib/adjudication";
import { formatTimestamp, toDate } from "../../lib/format";
import { withinWindow } from "../../lib/timeWindow";
import { verdictMeta } from "../../lib/verdict";
import { useWindowState } from "../../lib/windowContext";
import { AdjudicationDetail } from "./AdjudicationDetail";

/**
 * Candidate notable events on a time axis.
 *
 * Each event carries a verdict once the phase-4 wind-conditioned graph has
 * adjudicated it — GENUINE_EVENT / LIKELY_FAULT / AMBIGUOUS — and the field stays
 * null (rendered "pending adjudication") until then. The chip is coloured by the
 * verdict, and selecting an event opens its full evidence bundle below. An
 * unrecognised verdict string is shown verbatim; the dashboard never invents one.
 */

export type EventTone = "fault" | "degraded" | "neutral";

const VERDICT_TONE_CLASS = {
  verified: "prov-state-verified",
  degraded: "prov-state-degraded",
  fault: "prov-state-fault",
  unknown: "text-text-tertiary",
} as const;

/** Category and severity together, so shape and colour both carry meaning. */
export function eventTone(event: ProvEvent): EventTone {
  if (event.severity === "critical" || event.severity === "high") return "fault";
  if (event.severity === "medium" || event.severity === "low") return "degraded";
  return severityTone(event.reason_code);
}

const CATEGORY_MARK: Record<string, string> = {
  structural: "square",
  physical: "triangle",
  statistical: "diamond",
  coverage: "circle",
  trust: "circle",
};

export function eventMark(event: ProvEvent): string {
  const category = reasonCode(event.reason_code)?.category ?? event.category;
  return CATEGORY_MARK[category] ?? "circle";
}

export interface PlottedEvent {
  event: ProvEvent;
  /** 0-1 across the axis. */
  position: number;
  tone: EventTone;
  mark: string;
}

export function plotEvents(
  events: readonly ProvEvent[],
  start: Date | null,
  end: Date | null,
): { plotted: PlottedEvent[]; start: Date | null; end: Date | null } {
  if (events.length === 0) return { plotted: [], start, end };

  const times = events
    .map((event) => toDate(event.timestamp_utc))
    .filter((date): date is Date => date !== null);
  if (times.length === 0) return { plotted: [], start, end };

  const axisStart = start ?? new Date(Math.min(...times.map((t) => t.getTime())));
  const axisEnd = end ?? new Date(Math.max(...times.map((t) => t.getTime())));
  // Every event at one instant would divide by zero; a degenerate axis puts them
  // all at the midpoint rather than at the left edge.
  const span = axisEnd.getTime() - axisStart.getTime();

  const plotted = events
    .map((event) => {
      const at = toDate(event.timestamp_utc);
      if (!at) return null;
      return {
        event,
        position: span > 0 ? (at.getTime() - axisStart.getTime()) / span : 0.5,
        tone: eventTone(event),
        mark: eventMark(event),
      };
    })
    .filter((item): item is PlottedEvent => item !== null)
    .sort((a, b) => a.position - b.position);

  return { plotted, start: axisStart, end: axisEnd };
}

const TONE_CLASS: Record<EventTone, string> = {
  fault: "prov-state-fault",
  degraded: "prov-state-degraded",
  neutral: "prov-state-unknown",
};

function Mark({ mark, size = 12 }: { mark: string; size?: number }) {
  const c = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
      {mark === "square" && <rect x={1} y={1} width={size - 2} height={size - 2} fill="currentColor" />}
      {mark === "triangle" && (
        <path d={`M ${c} 1 L ${size - 1} ${size - 1} L 1 ${size - 1} Z`} fill="currentColor" />
      )}
      {mark === "diamond" && (
        <path d={`M ${c} 1 L ${size - 1} ${c} L ${c} ${size - 1} L 1 ${c} Z`} fill="currentColor" />
      )}
      {mark === "circle" && <circle cx={c} cy={c} r={c - 1} fill="currentColor" />}
    </svg>
  );
}

function VerdictChip({ verdict }: { verdict: string | null | undefined }) {
  const meta = verdictMeta(verdict);
  return (
    <span
      className={`rounded-sm border border-current px-2 text-caption ${VERDICT_TONE_CLASS[meta.tone]}`}
      data-testid="event-verdict"
      data-verdict-kind={meta.kind}
    >
      {meta.label}
    </span>
  );
}

export function EventTimeline() {
  const events = useEvents();
  const { resolved } = useWindowState();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedEventId = searchParams.get("event");

  const inWindow = useMemo(
    () =>
      (events.data ?? []).filter((event) =>
        resolved.start === null ? true : withinWindow(event.timestamp_utc, resolved),
      ),
    [events.data, resolved],
  );

  const { plotted, start, end } = useMemo(
    () =>
      plotEvents(
        inWindow,
        resolved.start ? new Date(resolved.start) : null,
        resolved.end ? new Date(resolved.end) : null,
      ),
    [inWindow, resolved],
  );

  const selectedEvent = useMemo(
    () => (events.data ?? []).find((event) => String(event.id) === selectedEventId) ?? null,
    [events.data, selectedEventId],
  );
  const selectedAdjudication = useMemo(
    () => (selectedEvent ? parseAdjudication(selectedEvent.evidence) : null),
    [selectedEvent],
  );

  if (events.isLoading) return <LoadingState label="Loading events" />;
  if (events.error) {
    return <ErrorState error={events.error} what="load the event list" onRetry={events.refetch} />;
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4" aria-label="Event timeline">
      <header>
        <h2 className="text-heading">Events</h2>
        <p className="text-caption text-text-tertiary">
          {plotted.length} candidate event{plotted.length === 1 ? "" : "s"} in the{" "}
          {resolved.label.toLowerCase()} window. Adjudication — deciding whether an event is a real
          plume or a sensor fault — runs over the wind-conditioned graph; select an event to see its
          verdict and the evidence behind it.
        </p>
      </header>

      {plotted.length === 0 ? (
        <div className="prov-panel">
          <EmptyState
            title="No events in this window"
            description="Widen the time window, or load a data drop with `make demo`. Events are ranked candidates from the audit, not alerts."
          />
        </div>
      ) : (
        <>
          {/* ------------------------------------------------------ the axis */}
          <div className="prov-panel p-4">
            <div className="relative h-8" data-testid="timeline-axis">
              <div className="absolute left-0 right-0 top-4 h-px bg-border-strong" />
              {plotted.map(({ event, position, tone, mark }) => (
                <button
                  key={event.id}
                  type="button"
                  className={`absolute top-1 -translate-x-2 ${TONE_CLASS[tone]}`}
                  style={{ left: `${position * 100}%` }}
                  data-testid="timeline-mark"
                  data-event-id={event.id}
                  data-tone={tone}
                  data-mark={mark}
                  aria-label={`${event.headline} at ${formatTimestamp(event.timestamp_utc)}, ${verdictMeta(event.verdict).label}`}
                  title={`${event.headline} — ${formatTimestamp(event.timestamp_utc)}`}
                  onClick={() =>
                    setSearchParams((previous) => {
                      const next = new URLSearchParams(previous);
                      next.set("event", String(event.id));
                      return next;
                    })
                  }
                >
                  <Mark mark={mark} />
                </button>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-micro text-text-tertiary">
              <span>{formatTimestamp(start?.toISOString())}</span>
              <span>{formatTimestamp(end?.toISOString())}</span>
            </div>
          </div>

          {/* ------------------------------------------------------ the list */}
          <ol className="m-0 list-none space-y-2 p-0" data-testid="timeline-list">
            {plotted.map(({ event, tone, mark }) => (
              <li key={event.id} className="prov-panel p-3" data-testid="timeline-event">
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className={TONE_CLASS[tone]}>
                    <Mark mark={mark} />
                  </span>
                  <span className="font-mono text-caption text-text-tertiary">#{event.rank}</span>
                  <h3 className="text-subhead">{event.headline}</h3>
                  <VerdictChip verdict={event.verdict} />
                  {String(event.id) === selectedEventId && (
                    <span className="text-micro text-interactive">selected</span>
                  )}
                </div>
                {/* The headline above *is* the rendered sentence, computed by the
                    audit engine. Repeating it here would say the same thing twice;
                    the code chip carries the registry key and the full sentence in
                    its accessible name. */}
                <div className="mt-1">
                  <ReasonCodeBadge
                    code={event.reason_code}
                    variant="code"
                    evidence={evidenceFor(event)}
                  />
                </div>
                <p className="mt-1 text-caption text-text-tertiary">
                  {event.station_id} · {event.parameter} · {formatTimestamp(event.timestamp_utc)} ·{" "}
                  {event.severity}
                </p>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    className="prov-button"
                    data-testid="event-adjudication-toggle"
                    onClick={() =>
                      setSearchParams((previous) => {
                        const next = new URLSearchParams(previous);
                        if (String(event.id) === selectedEventId) next.delete("event");
                        else next.set("event", String(event.id));
                        return next;
                      })
                    }
                  >
                    {String(event.id) === selectedEventId ? "Hide adjudication" : "Adjudication"}
                  </button>
                  <Link
                    className="prov-button"
                    to={`/evidence?station=${encodeURIComponent(event.station_id)}&code=${encodeURIComponent(event.reason_code)}`}
                  >
                    View evidence
                  </Link>
                  <Link
                    className="prov-button"
                    to={`/?station=${encodeURIComponent(event.station_id)}`}
                  >
                    Show on map
                  </Link>
                </div>
              </li>
            ))}
          </ol>

          {selectedEvent &&
            (selectedAdjudication ? (
              <AdjudicationDetail event={selectedEvent} adjudication={selectedAdjudication} />
            ) : (
              <p
                className="prov-panel p-3 text-caption text-text-tertiary"
                data-testid="adjudication-pending"
              >
                This event has not been adjudicated yet. Run `prov graph adjudicate-db` after loading
                a drop; the verdict and its evidence appear here once the wind graph has weighed it.
              </p>
            ))}
        </>
      )}
    </section>
  );
}
