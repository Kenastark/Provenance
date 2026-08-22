/**
 * Number and time formatting.
 *
 * The corpus is UTC and the audit reasons in UTC, so the dashboard displays UTC
 * and says so. Silently localising timestamps would mean an operator comparing the
 * dashboard against the audit report sees two different times for one event.
 */

const NUMBER = new Intl.NumberFormat("en-GB");
const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});
const DATE_ONLY = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  timeZone: "UTC",
});

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return NUMBER.format(value);
}

/** A trust score, always to two places so a column of them stays aligned. */
export function formatTrust(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

/** A rate in [0, 1] rendered as a percentage. */
export function formatRateAsPercent(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatMeasurement(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const magnitude = Math.abs(value);
  const digits = magnitude >= 100 ? 1 : magnitude >= 1 ? 2 : 4;
  const text = Number(value.toFixed(digits)).toString();
  return unit ? `${text} ${unit}` : text;
}

function parseUtc(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  // The API emits naive ISO strings that are UTC by contract. Date.parse would
  // read a bare "2026-08-08T12:00:00" as *local* time, which shifts every
  // timestamp on the screen by the viewer's offset.
  const normalised = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(normalised);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatTimestamp(iso: string | null | undefined): string {
  const date = parseUtc(iso);
  return date ? `${DATE_TIME.format(date)} UTC` : "—";
}

export function formatDate(iso: string | null | undefined): string {
  const date = parseUtc(iso);
  return date ? DATE_ONLY.format(date) : "—";
}

export function toDate(iso: string | null | undefined): Date | null {
  return parseUtc(iso);
}

/**
 * "3 days ago" / "in 2 hours", relative to `now`.
 *
 * The default is the real wall clock only because there is no other sensible
 * fallback for a caller with no window context at all. Anywhere the dataset's own
 * anchor is available (`useWindowState().anchor` - see `lib/windowContext.tsx`),
 * pass it explicitly: the corpus is a fixed historical drop, not a live feed, so a
 * station's last reading drifting further "ago" every day the demo sits unopened,
 * against a browser clock that keeps moving while the data does not, reads as the
 * station going stale when nothing about it has changed.
 */
export function formatRelative(iso: string | null | undefined, now: Date = new Date()): string {
  const date = parseUtc(iso);
  if (!date) return "—";
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const absolute = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto" });
  if (absolute < 90) return formatter.format(Math.round(seconds), "second");
  if (absolute < 5400) return formatter.format(Math.round(seconds / 60), "minute");
  if (absolute < 129600) return formatter.format(Math.round(seconds / 3600), "hour");
  return formatter.format(Math.round(seconds / 86400), "day");
}

/** A duration in hours, spoken the way the reason-code sentences speak. */
export function formatDurationHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || Number.isNaN(hours)) return "—";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 48) return `${Math.round(hours)} h`;
  return `${Math.round(hours / 24)} days`;
}

/** A short, stable label for a station in tight chrome (map markers, chips). */
export function stationShortLabel(stationId: string): string {
  const tail = stationId.split(/[-_]/).pop();
  return tail && tail.length <= 4 ? tail : stationId.slice(-4);
}
