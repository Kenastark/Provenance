import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useAuditRuns, useQualitySummary } from "../api/queries";
import type { AuditRun } from "../api/client";
import { toDate } from "./format";
import {
  DEFAULT_TIME_WINDOW,
  resolveWindow,
  type ResolvedWindow,
  type TimeWindowKey,
} from "./timeWindow";

/**
 * The time window, shared by every screen, anchored to the data.
 *
 * The corpus is a historical drop rather than a live feed, so "last 24 hours" has
 * to mean 24 hours of *readings*. The anchor is therefore the newest reading in the
 * network - the maximum `last_reading_at` across stations - and not `Date.now()`,
 * and not the audit run's `generated_at` either. Both of those are the time the
 * question was asked rather than the time the data covers: a May corpus audited in
 * August has a perfectly healthy run whose trailing week contains no readings at
 * all, and every screen would come up empty while nothing was actually wrong.
 *
 * The run's `generated_at` is the fallback for a run with no readings behind it,
 * which is the only case where there is nothing better to anchor on.
 */

interface WindowContextValue {
  timeWindow: TimeWindowKey;
  setTimeWindow: (next: TimeWindowKey) => void;
  resolved: ResolvedWindow;
  /** Newest audit run, or null before one has been loaded. */
  latestRun: AuditRun | null;
  anchor: Date | null;
  isLoading: boolean;
  error: unknown;
}

const WindowContext = createContext<WindowContextValue | null>(null);

export function WindowProvider({ children }: { children: ReactNode }) {
  const [timeWindow, setTimeWindow] = useState<TimeWindowKey>(DEFAULT_TIME_WINDOW);
  const runs = useAuditRuns();
  const quality = useQualitySummary();

  const latestRun = useMemo(() => {
    if (!runs.data || runs.data.length === 0) return null;
    return [...runs.data].sort((a, b) => b.generated_at.localeCompare(a.generated_at))[0] ?? null;
  }, [runs.data]);

  const newestReading = useMemo(() => {
    const stamps = (quality.data?.stations ?? [])
      .map((station) => station.last_reading_at)
      .filter((stamp): stamp is string => Boolean(stamp));
    if (stamps.length === 0) return null;
    return stamps.reduce((newest, stamp) => (stamp > newest ? stamp : newest));
  }, [quality.data]);

  const anchor = useMemo(
    () => toDate(newestReading) ?? toDate(latestRun?.generated_at),
    [newestReading, latestRun],
  );

  const value = useMemo<WindowContextValue>(
    () => ({
      timeWindow,
      setTimeWindow,
      resolved: resolveWindow(timeWindow, anchor),
      latestRun,
      anchor,
      isLoading: runs.isLoading || quality.isLoading,
      error: runs.error,
    }),
    [timeWindow, anchor, latestRun, runs.isLoading, runs.error, quality.isLoading],
  );

  return <WindowContext.Provider value={value}>{children}</WindowContext.Provider>;
}

export function useWindowState(): WindowContextValue {
  const context = useContext(WindowContext);
  if (!context) throw new Error("useWindowState must be used inside a WindowProvider");
  return context;
}
