import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { ProvEvent } from "../../api/client";
import { evidenceFor, reasonCode, severityTone } from "../../api/reason-codes";
import { ReasonCodeBadge } from "../../components/ReasonCodeBadge";
import { useEvents } from "../../api/queries";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { formatTimestamp, toDate } from "../../lib/format";
import { withinWindow } from "../../lib/timeWindow";
import { useWindowState } from "../../lib/windowContext";

/**
 * Candidate notable events on a time axis.
 *
 * The verdict column says "pending adjudication" and will keep saying it until the
 * phase-4 wind-conditioned graph exists to decide. The API already carries the
 * field - it is null, not absent - so nothing about this screen changes shape when
 * adjudication lands, only the words change. Writing a plausible-looking verdict
 * now would be the exact failure this product exists to detect.
 */

export type EventTone = "fault" | "degraded" | "neutral";

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

export function EventTimeline() {
  const events = useEvents();
  const { resolved } = useWindowState();
  const [, setSearchParams] = useSearchParams();

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
          plume or a sensor fault — needs the wind-conditioned graph and lands in phase 4.
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
                  aria-label={`${event.headline} at ${formatTimestamp(event.timestamp_utc)}, pending adjudication`}
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
                  <span
                    className="rounded-sm border border-border px-2 text-caption text-text-tertiary"
                    data-testid="event-verdict"
                  >
                    {event.verdict ?? "pending adjudication"}
                  </span>
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
        </>
      )}
    </section>
  );
}
