import type { TrustState } from "../lib/trust";
import { trustStateLabel, trustStateShape } from "../lib/trust";

/**
 * The shape channel.
 *
 * Colour is never the only channel carrying state (token file, rule 4). Each trust
 * state has a distinct silhouette, so the map and the tables read correctly for a
 * colourblind operator, in a greyscale print, and on a projector that has eaten
 * the saturation - which is exactly the situation a demo runs in.
 *
 * The silhouettes come from the `--prov-shape-*` tokens, lifted into TypeScript by
 * the contract generator so the token file stays the single source.
 */

export interface StateGlyphProps {
  state: TrustState;
  size?: number;
  /** Rendered inside the SVG for screen readers unless the glyph is decorative. */
  decorative?: boolean;
  className?: string;
}

export function StateGlyph({ state, size = 12, decorative = false, className }: StateGlyphProps) {
  const shape = trustStateShape(state);
  const label = trustStateLabel(state);
  const r = size / 2 - 1;
  const c = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      data-shape={shape}
      data-state={state}
      role={decorative ? "presentation" : "img"}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : label}
      focusable="false"
    >
      {!decorative && <title>{label}</title>}
      {shape === "circle-filled" && <circle cx={c} cy={c} r={r} fill="currentColor" />}

      {shape === "circle-half" && (
        <>
          <circle cx={c} cy={c} r={r} fill="none" stroke="currentColor" strokeWidth={2} />
          <path d={`M ${c} ${c - r} A ${r} ${r} 0 0 1 ${c} ${c + r} Z`} fill="currentColor" />
        </>
      )}

      {shape === "circle-barred" && (
        <>
          <circle cx={c} cy={c} r={r} fill="none" stroke="currentColor" strokeWidth={2} />
          <line
            x1={c - r * 0.7}
            y1={c + r * 0.7}
            x2={c + r * 0.7}
            y2={c - r * 0.7}
            stroke="currentColor"
            strokeWidth={2}
          />
        </>
      )}

      {shape === "ring-dashed" && (
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeDasharray="3 2"
        />
      )}

      {shape === "hatch" && (
        <>
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeDasharray="2 2"
          />
          <line
            x1={c - r * 0.6}
            y1={c + r * 0.6}
            x2={c + r * 0.6}
            y2={c - r * 0.6}
            stroke="currentColor"
            strokeWidth={1.5}
          />
        </>
      )}
    </svg>
  );
}
