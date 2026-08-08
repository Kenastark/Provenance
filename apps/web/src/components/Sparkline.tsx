import { useId } from "react";
import { formatMeasurement, formatTimestamp } from "../lib/format";

/**
 * A small inline series, drawn as plain SVG.
 *
 * Deliberately not a charting library: a sparkline has no axes, no tooltip, and no
 * responsive container, and hand-drawn SVG renders identically under jsdom, in a
 * Playwright screenshot, and on a projector. The larger evidence charts do use
 * Recharts, where the axes and interaction earn it.
 *
 * Gaps are gaps. A null reading breaks the path rather than being interpolated
 * across - drawing a straight line through missing data would be the dashboard
 * telling the same comfortable lie the audit exists to catch.
 */

export interface SparkPoint {
  t: string;
  value: number | null;
  /** True when the audit flagged this exact cell. */
  flagged?: boolean;
}

export interface SparklineProps {
  points: readonly SparkPoint[];
  /** Accessible name, e.g. "PM10 at DEB-KER11". */
  label: string;
  unit?: string | null;
  width?: number;
  height?: number;
  className?: string;
}

interface Scaled {
  x: number;
  y: number;
  point: SparkPoint;
}

export function Sparkline({
  points,
  label,
  unit,
  width = 160,
  height = 32,
  className,
}: SparklineProps) {
  const titleId = useId();
  const values = points.map((p) => p.value).filter((v): v is number => v !== null);

  if (points.length === 0 || values.length === 0) {
    return (
      <span className="text-caption text-text-tertiary" data-testid="sparkline-empty">
        No data in window
      </span>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series still has to be visible, so a zero range gets a nominal one and
  // draws down the middle rather than collapsing onto the baseline. R12 (zero
  // variance) series are exactly this case, and they are the point.
  const range = max - min || 1;
  const padding = 2;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const step = points.length > 1 ? innerWidth / (points.length - 1) : 0;

  const scaled: (Scaled | null)[] = points.map((point, index) =>
    point.value === null
      ? null
      : {
          x: padding + index * step,
          y: padding + innerHeight - ((point.value - min) / range) * innerHeight,
          point,
        },
  );

  // Build one path per contiguous run of present values.
  const segments: string[] = [];
  let current: string[] = [];
  for (const item of scaled) {
    if (item === null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
      continue;
    }
    current.push(`${current.length === 0 ? "M" : "L"} ${item.x.toFixed(2)} ${item.y.toFixed(2)}`);
  }
  if (current.length > 1) segments.push(current.join(" "));

  const flagged = scaled.filter(
    (item): item is Scaled => item !== null && Boolean(item.point.flagged),
  );

  const first = points[0];
  const last = points[points.length - 1];
  const summary =
    `${label}: ${points.length} points from ${formatTimestamp(first?.t)} to ${formatTimestamp(last?.t)}, ` +
    `range ${formatMeasurement(min, unit)} to ${formatMeasurement(max, unit)}` +
    (flagged.length > 0 ? `, ${flagged.length} flagged` : "");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-labelledby={titleId}
      data-testid="sparkline"
      data-points={points.length}
      data-flagged={flagged.length}
      focusable="false"
    >
      <title id={titleId}>{summary}</title>
      {segments.map((d) => (
        <path
          key={d}
          d={d}
          fill="none"
          stroke="var(--prov-chart-series-1)"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
      {flagged.map((item) => (
        <circle
          key={item.point.t}
          cx={item.x}
          cy={item.y}
          r={2.5}
          fill="var(--prov-state-fault)"
          data-testid="sparkline-flag"
        />
      ))}
    </svg>
  );
}
