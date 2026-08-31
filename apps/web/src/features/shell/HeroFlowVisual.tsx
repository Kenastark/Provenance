import { useEffect, useState } from "react";

/**
 * The Layer 1 -> Layer 2 -> trust score flow, illustrated.
 *
 * Purely decorative (`aria-hidden`) — it exists to make the sign-in screen's
 * "Layer 1 reports, Layer 2 audits" sentence visible at a glance, the same way
 * a product screenshot would. The station reading and the trust score are a
 * worked example for the graphic, not a claim about any real reading —
 * nothing here is wired to `/v1/*`. The station id (DEB-KER18) and the
 * reason code (R22 — PLUME_CORROBORATED, the registry's GENUINE_EVENT
 * verdict, see `src/provenance/config/reason_codes.py`) are both real
 * identifiers from the live system; the reading and score attached to them
 * here are illustrative. Colour follows the state
 * semantics in `design/tokens/tokens.css`: amber for an unverified reading,
 * Trust Blue for the engine's own chrome, Sentinel Green for what it
 * verifies — each card's border picks up its own theme colour instead of the
 * neutral `prov-panel` default.
 *
 * Each card is header (eyebrow) + sub-header (identity) at a fixed top
 * position, then the graphic, then a status pill pinned to the card's bottom
 * edge via `mt-auto` — so the three headers land on the same line and the
 * three status pills land on the same line, regardless of how tall each
 * card's own graphic is.
 */

export const CARD_SIZE = 240;
/** The gap between cards - card size is untouched; only the spacing (and so
 * the connector lines' own length) changes here. Each connector `<svg>` is
 * sized to exactly this width with zero extra margin on either side (the row
 * uses `gap-0`), so its line always spans border-to-border with no gap. */
const CONNECTOR_WIDTH = 140;
/** Exported so the sign-in screen's write-up can be widened to the same edges
 * as this row, rather than the two blocks drifting to different margins. */
export const HERO_ROW_WIDTH = CARD_SIZE * 3 + CONNECTOR_WIDTH * 2;

/** Each card's graphic sits in a zone this tall, centred, before the caption
 * and pill that follow it - the dial is the tallest graphic, so every card
 * uses its height. Without this, a card whose own graphic is short (card 1's
 * reading, card 2's graph) ends up with all its slack absorbed as extra space
 * right before its pill (that's what `mt-auto` does), which pins every pill to
 * the same line but leaves the caption *above* each pill at a different
 * height per card. Fixing the zone height first means the caption row lines
 * up too, with no per-card tuning. */
const GRAPHIC_ZONE_HEIGHT = 112;
const TRUST_SCORE = 0.984;
const DIAL_SIZE = GRAPHIC_ZONE_HEIGHT;
const DIAL_RADIUS = 44;
const DIAL_STROKE = 8;
const DIAL_CIRCUMFERENCE = 2 * Math.PI * DIAL_RADIUS;
const DIAL_EMPTY_OFFSET = DIAL_CIRCUMFERENCE;
const DIAL_FULL_OFFSET = DIAL_CIRCUMFERENCE * (1 - TRUST_SCORE);

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

const headerClass = "font-display text-caption font-bold whitespace-nowrap";
const subheaderClass = "font-display text-micro font-semibold text-text whitespace-nowrap";
const pillClass = "mt-auto rounded-sm px-2 py-1 text-micro font-semibold uppercase tracking-wide";
const captionClass = "text-micro text-text-tertiary";

export function HeroFlowVisual() {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div aria-hidden="true" className="flex items-center justify-center gap-0 py-2">
      <div
        className="prov-panel relative z-10 flex shrink-0 flex-col items-center gap-1 border-ambiguous p-4 text-center"
        style={{ width: CARD_SIZE, height: CARD_SIZE }}
      >
        <span className={`${headerClass} text-ambiguous`}>LAYER 1</span>
        <span className={subheaderClass}>Green Sentinel Network</span>
        <span
          className="flex flex-col items-center justify-center gap-1"
          style={{ height: GRAPHIC_ZONE_HEIGHT }}
        >
          <span className="font-display text-subhead font-semibold text-text">DEB-KER18</span>
          <span className="flex items-center gap-2">
            <span
              className="hero-pulse-dot h-3 w-3 shrink-0 rounded-full"
              style={{ background: "var(--prov-state-ambiguous)" }}
            />
            <span className="font-display text-display-l font-semibold text-text">
              180&nbsp;&micro;g/m&sup3;
            </span>
          </span>
        </span>
        <span className={captionClass}>Physical Sensor</span>
        <span
          className={`${pillClass} text-ambiguous`}
          style={{ background: "color-mix(in srgb, var(--prov-state-ambiguous) 18%, transparent)" }}
        >
          Unverified spike
        </span>
      </div>

      <svg
        width={CONNECTOR_WIDTH}
        height="8"
        className="hero-connector-flow shrink-0 self-center"
        viewBox={`0 0 ${CONNECTOR_WIDTH} 8`}
      >
        <line
          x1="0"
          y1="4"
          x2={CONNECTOR_WIDTH}
          y2="4"
          stroke="var(--prov-interactive)"
          strokeWidth="2"
          strokeDasharray="5 4"
        />
      </svg>

      <div
        className="prov-panel relative z-20 flex shrink-0 flex-col items-center gap-1 border-interactive p-4 text-center"
        style={{
          width: CARD_SIZE,
          height: CARD_SIZE,
          background: "color-mix(in srgb, var(--prov-surface) 55%, transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
        }}
      >
        <span className={`${headerClass} text-interactive`}>LAYER 2</span>
        <span className={subheaderClass}>Provenance AI Engine</span>
        <span
          className="flex items-center justify-center"
          style={{ height: GRAPHIC_ZONE_HEIGHT }}
        >
          <svg width="150" height="90" viewBox="0 0 150 90" className="hero-graph-glow">
            <g transform="rotate(16 75 41)">
              <line x1="26" y1="68" x2="75" y2="20" stroke="var(--prov-interactive)" strokeWidth="2" />
              <line x1="75" y1="20" x2="125" y2="63" stroke="var(--prov-interactive)" strokeWidth="2" />
              <line
                x1="26"
                y1="68"
                x2="125"
                y2="63"
                stroke="var(--prov-interactive)"
                strokeWidth="2"
                strokeDasharray="3 3"
              />
              <circle cx="26" cy="68" r="6" fill="var(--prov-state-verified)" />
              <circle cx="75" cy="20" r="8" fill="var(--prov-interactive)" />
              <circle cx="125" cy="63" r="6" fill="var(--prov-state-verified)" />
            </g>
          </svg>
        </span>
        <span className="flex flex-col gap-1">
          <span className={captionClass}>Spatial + Wind Adjudication</span>
          <span className={captionClass}>Anomalies detection</span>
        </span>
        <span
          className={`${pillClass} text-interactive`}
          style={{ background: "color-mix(in srgb, var(--prov-interactive) 18%, transparent)" }}
        >
          HST-GAT model
        </span>
      </div>

      <svg
        width={CONNECTOR_WIDTH}
        height="8"
        className="shrink-0 self-center"
        viewBox={`0 0 ${CONNECTOR_WIDTH} 8`}
      >
        <line x1="0" y1="4" x2={CONNECTOR_WIDTH} y2="4" stroke="var(--prov-state-verified)" strokeWidth="2" />
      </svg>

      <div
        className="prov-panel relative z-10 flex shrink-0 flex-col items-center gap-1 border-verified p-4 text-center"
        style={{ width: CARD_SIZE, height: CARD_SIZE }}
      >
        <span className={`${headerClass} text-verified`}>OUTPUT</span>
        <span className={subheaderClass}>Trust Score</span>
        <div className="relative grid place-items-center" style={{ width: DIAL_SIZE, height: DIAL_SIZE }}>
          <svg width={DIAL_SIZE} height={DIAL_SIZE} viewBox={`0 0 ${DIAL_SIZE} ${DIAL_SIZE}`} className="-rotate-90">
            <circle
              cx={DIAL_SIZE / 2}
              cy={DIAL_SIZE / 2}
              r={DIAL_RADIUS}
              fill="none"
              stroke="var(--prov-border)"
              strokeWidth={DIAL_STROKE}
            />
            <circle
              cx={DIAL_SIZE / 2}
              cy={DIAL_SIZE / 2}
              r={DIAL_RADIUS}
              fill="none"
              stroke="var(--prov-state-verified)"
              strokeWidth={DIAL_STROKE}
              strokeLinecap="round"
              strokeDasharray={DIAL_CIRCUMFERENCE}
              strokeDashoffset={reducedMotion ? DIAL_FULL_OFFSET : DIAL_EMPTY_OFFSET}
            >
              {!reducedMotion && (
                <animate
                  attributeName="stroke-dashoffset"
                  values={`${DIAL_EMPTY_OFFSET};${DIAL_FULL_OFFSET};${DIAL_FULL_OFFSET};${DIAL_EMPTY_OFFSET}`}
                  keyTimes="0;0.45;0.75;1"
                  dur="3.4s"
                  begin="0.2s"
                  repeatCount="indefinite"
                  calcMode="spline"
                  keySplines="0.2 0 0 1;0 0 1 1;0.2 0 0 1"
                />
              )}
            </circle>
          </svg>
          <span className="prov-numeric absolute font-display text-heading font-bold text-verified">
            98.4%
          </span>
        </div>
        <span className="font-mono text-micro text-text-tertiary">R22 &mdash; PLUME_CORROBORATED</span>
        <span
          className={`${pillClass} text-verified`}
          style={{ background: "color-mix(in srgb, var(--prov-state-verified) 18%, transparent)" }}
        >
          Human Sign-off
        </span>
      </div>
    </div>
  );
}
