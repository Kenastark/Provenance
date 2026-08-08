/**
 * The global time window.
 *
 * The corpus is a fixed 30-day historical drop, not a live feed, so "last 24 hours"
 * has to mean 24 hours back from the newest reading in the data rather than from
 * the wall clock - otherwise every window is empty and the demo looks broken.
 * `resolveWindow` therefore takes the anchor explicitly, and the anchor comes from
 * the data (the latest audit run's generated_at, or the latest reading).
 */

export type TimeWindowKey = "24h" | "7d" | "corpus";

export interface TimeWindowOption {
  key: TimeWindowKey;
  label: string;
  /** Null means "no lower bound": the full corpus. */
  hours: number | null;
  description: string;
}

export const TIME_WINDOWS: readonly TimeWindowOption[] = [
  { key: "24h", label: "Last 24h", hours: 24, description: "24 hours back from the newest reading" },
  { key: "7d", label: "Last 7d", hours: 24 * 7, description: "7 days back from the newest reading" },
  { key: "corpus", label: "Full corpus", hours: null, description: "Every reading in the loaded drop" },
];

export const DEFAULT_TIME_WINDOW: TimeWindowKey = "7d";

export interface ResolvedWindow {
  key: TimeWindowKey;
  /** ISO instant, or null for the full corpus. */
  start: string | null;
  end: string | null;
  label: string;
}

export function timeWindowOption(key: TimeWindowKey): TimeWindowOption {
  return TIME_WINDOWS.find((option) => option.key === key) ?? TIME_WINDOWS[TIME_WINDOWS.length - 1]!;
}

export function resolveWindow(key: TimeWindowKey, anchor: Date | null): ResolvedWindow {
  const option = timeWindowOption(key);
  if (option.hours === null || anchor === null) {
    return { key: option.key, start: null, end: null, label: option.label };
  }
  const start = new Date(anchor.getTime() - option.hours * 3600_000);
  return {
    key: option.key,
    start: start.toISOString(),
    end: anchor.toISOString(),
    label: option.label,
  };
}

/** True when `iso` falls inside the resolved window. Unbounded windows accept everything. */
export function withinWindow(iso: string | null | undefined, window: ResolvedWindow): boolean {
  if (!iso) return false;
  if (window.start === null) return true;
  const normalised = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const at = new Date(normalised).getTime();
  if (Number.isNaN(at)) return false;
  const start = new Date(window.start).getTime();
  const end = window.end ? new Date(window.end).getTime() : Number.POSITIVE_INFINITY;
  return at >= start && at <= end;
}
