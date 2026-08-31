import { useEffect, useState } from "react";

/**
 * The Layer 1 -> Layer 2 -> trust score flow, illustrated.
 *
 * Purely decorative (`aria-hidden`) — it exists to make the sign-in screen's
 * "Layer 1 reports, Layer 2 audits" sentence visible at a glance, the same way
 * a product screenshot would. The station reading and the trust score are a
 * worked example for the graphic, not a claim about any real reading —
 * nothing here is wired to `/v1/*`. The station id (DEB-KER18) and the reason
 * code (R22 — PLUME_CORROBORATED, the registry's GENUINE_EVENT verdict, see
 * `src/provenance/config/reason_codes.py`) are both real identifiers from the
 * live system; the reading and score attached to them here are illustrative.
 * Colour follows the state semantics in `design/tokens/tokens.css`: amber for
 * an unverified reading, Trust Blue for the engine's own chrome, Sentinel
 * Green for what it verifies — each card's border picks up its own theme
 * colour instead of the neutral `prov-panel` default.
 */

const CARD_SIZE = 320;
const TRUST_SCORE = 0.984;
const DIAL_RADIUS = 58;
const DIAL_CIRCUMFERENCE = 2 * Math.PI * DIAL_RADIUS;
const DIAL_TARGET_OFFSET = DIAL_CIRCUMFERENCE * (1 - TRUST_SCORE);

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

export function HeroFlowVisual() {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div aria-hidden="true" className="flex w-full max-w-6xl items-center justify-center gap-0 py-2">
      <div
        className="prov-panel relative z-10 flex shrink-0 flex-col items-center justify-center gap-3 border-ambiguous p-6 text-center"
        style={{ width: CARD_SIZE, height: CARD_SIZE }}
      >
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-ambiguous">
          Layer 1 &middot; Physical
        </span>
        <span className="font-display text-subhead font-semibold text-text">DEB-KER18</span>
        <span className="flex items-center gap-2">
          <span
            className="hero-pulse-dot h-3 w-3 shrink-0 rounded-full"
            style={{ background: "var(--prov-state-ambiguous)" }}
          />
          <span className="font-display text-heading font-semibold text-text">
            180&nbsp;&micro;g/m&sup3;
          </span>
        </span>
        <span
          className="rounded-sm px-2 py-1 text-micro font-semibold uppercase tracking-wide text-ambiguous"
          style={{ background: "color-mix(in srgb, var(--prov-state-ambiguous) 18%, transparent)" }}
        >
          Unverified spike
        </span>
      </div>

      <svg width="56" height="8" className="hero-connector-flow shrink-0" viewBox="0 0 56 8">
        <line
          x1="0"
          y1="4"
          x2="56"
          y2="4"
          stroke="var(--prov-interactive)"
          strokeWidth="2"
          strokeDasharray="5 4"
        />
      </svg>

      <div
        className="prov-panel relative z-20 flex shrink-0 flex-col items-center justify-center gap-3 border-interactive p-6 text-center"
        style={{
          width: CARD_SIZE,
          height: CARD_SIZE,
          background: "color-mix(in srgb, var(--prov-surface) 55%, transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
        }}
      >
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-interactive">
          Layer 2 &middot; Engine
        </span>
        <span className="font-display text-subhead font-semibold text-text">HST-GAT model</span>
        <svg width="200" height="120" viewBox="0 0 200 120" className="hero-graph-glow">
          <g transform="rotate(16 100 55)">
            <line x1="34" y1="90" x2="100" y2="26" stroke="var(--prov-interactive)" strokeWidth="2" />
            <line x1="100" y1="26" x2="166" y2="84" stroke="var(--prov-interactive)" strokeWidth="2" />
            <line
              x1="34"
              y1="90"
              x2="166"
              y2="84"
              stroke="var(--prov-interactive)"
              strokeWidth="2"
              strokeDasharray="3 3"
            />
            <circle cx="34" cy="90" r="7" fill="var(--prov-state-verified)" />
            <circle cx="100" cy="26" r="11" fill="var(--prov-interactive)" />
            <circle cx="166" cy="84" r="7" fill="var(--prov-state-verified)" />
          </g>
        </svg>
        <span className="text-micro text-text-tertiary">Spatial + wind adjudication</span>
      </div>

      <svg width="56" height="8" className="shrink-0" viewBox="0 0 56 8">
        <line x1="0" y1="4" x2="56" y2="4" stroke="var(--prov-state-verified)" strokeWidth="2" />
      </svg>

      <div
        className="prov-panel relative z-10 flex shrink-0 flex-col items-center justify-center gap-3 border-verified p-6 text-center"
        style={{ width: CARD_SIZE, height: CARD_SIZE }}
      >
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-verified">
          Trust score
        </span>
        <div className="relative grid place-items-center" style={{ width: 148, height: 148 }}>
          <svg width="148" height="148" viewBox="0 0 148 148" className="-rotate-90">
            <circle cx="74" cy="74" r={DIAL_RADIUS} fill="none" stroke="var(--prov-border)" strokeWidth="10" />
            <circle
              cx="74"
              cy="74"
              r={DIAL_RADIUS}
              fill="none"
              stroke="var(--prov-state-verified)"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={DIAL_CIRCUMFERENCE}
              strokeDashoffset={reducedMotion ? DIAL_TARGET_OFFSET : DIAL_CIRCUMFERENCE}
            >
              {!reducedMotion && (
                <animate
                  attributeName="stroke-dashoffset"
                  from={DIAL_CIRCUMFERENCE}
                  to={DIAL_TARGET_OFFSET}
                  dur="1.4s"
                  begin="0.2s"
                  fill="freeze"
                  calcMode="spline"
                  keySplines="0.2 0 0 1"
                  keyTimes="0;1"
                />
              )}
            </circle>
          </svg>
          <span className="prov-numeric absolute font-display text-display-l font-bold text-verified">
            98.4%
          </span>
        </div>
        <span
          className="rounded-sm px-2 py-1 text-micro font-semibold uppercase tracking-wide text-verified"
          style={{ background: "color-mix(in srgb, var(--prov-state-verified) 18%, transparent)" }}
        >
          Verified plume
        </span>
        <span className="font-mono text-micro text-text-tertiary">R22 &mdash; PLUME_CORROBORATED</span>
      </div>
    </div>
  );
}
