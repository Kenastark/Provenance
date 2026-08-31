/**
 * The Layer 1 -> Layer 2 -> trust score flow, illustrated.
 *
 * Purely decorative (`aria-hidden`) — it exists to make the sign-in screen's
 * "Layer 1 reports, Layer 2 audits" sentence visible at a glance, the same way
 * a product screenshot would. The station reading, the trust score, and the
 * reason code on the right are a worked example for the graphic, not a claim
 * about any real station — nothing here is wired to `/v1/*`. Colour follows
 * the state semantics in `design/tokens/tokens.css`: amber for an unverified
 * reading, Trust Blue for the engine's own chrome, Sentinel Green for what it
 * verifies.
 */
export function HeroFlowVisual() {
  return (
    <div
      aria-hidden="true"
      className="flex w-full max-w-3xl items-center justify-center gap-0 py-2"
    >
      <div className="prov-panel relative z-10 flex w-52 shrink-0 flex-col items-start gap-2 p-4 text-left">
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-text-tertiary">
          Layer 1 &middot; Physical
        </span>
        <span className="font-display text-subhead font-semibold text-text">Station #04</span>
        <span className="flex items-center gap-2">
          <span
            className="hero-pulse-dot h-2.5 w-2.5 shrink-0 rounded-full"
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

      <svg width="48" height="8" className="hero-connector-flow shrink-0" viewBox="0 0 48 8">
        <line
          x1="0"
          y1="4"
          x2="48"
          y2="4"
          stroke="var(--prov-interactive)"
          strokeWidth="2"
          strokeDasharray="5 4"
        />
      </svg>

      <div
        className="prov-panel relative z-20 flex w-60 shrink-0 flex-col items-center gap-2 border-interactive p-4 text-center"
        style={{
          background: "color-mix(in srgb, var(--prov-surface) 55%, transparent)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
        }}
      >
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-interactive">
          Layer 2 &middot; Engine
        </span>
        <span className="font-display text-subhead font-semibold text-text">HST-GAT model</span>
        <svg width="128" height="60" viewBox="0 0 128 60" className="hero-graph-glow">
          <line x1="18" y1="44" x2="64" y2="16" stroke="var(--prov-interactive)" strokeWidth="2" />
          <line x1="64" y1="16" x2="110" y2="40" stroke="var(--prov-interactive)" strokeWidth="2" />
          <line
            x1="18"
            y1="44"
            x2="110"
            y2="40"
            stroke="var(--prov-interactive)"
            strokeWidth="2"
            strokeDasharray="3 3"
          />
          <circle cx="18" cy="44" r="6" fill="var(--prov-state-verified)" />
          <circle cx="64" cy="16" r="8" fill="var(--prov-state-verified)" />
          <circle cx="110" cy="40" r="6" fill="var(--prov-state-verified)" />
        </svg>
        <span className="text-micro text-text-tertiary">Spatial + wind adjudication</span>
      </div>

      <svg width="48" height="8" className="shrink-0" viewBox="0 0 48 8">
        <line x1="0" y1="4" x2="48" y2="4" stroke="var(--prov-state-verified)" strokeWidth="2" />
      </svg>

      <div className="prov-panel relative z-10 flex w-48 shrink-0 flex-col items-center gap-2 border-interactive p-4 text-center">
        <span className="font-display text-micro font-semibold uppercase tracking-[0.2em] text-verified">
          Trust score
        </span>
        <div className="relative grid h-[72px] w-[72px] place-items-center">
          <svg width="72" height="72" viewBox="0 0 72 72" className="-rotate-90">
            <circle cx="36" cy="36" r="30" fill="none" stroke="var(--prov-border)" strokeWidth="6" />
            <circle
              cx="36"
              cy="36"
              r="30"
              fill="none"
              stroke="var(--prov-state-verified)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 30}
              strokeDashoffset={2 * Math.PI * 30 * (1 - 0.984)}
            />
          </svg>
          <span className="prov-numeric absolute font-display text-subhead font-bold text-verified">
            98.4%
          </span>
        </div>
        <span
          className="rounded-sm px-2 py-1 text-micro font-semibold uppercase tracking-wide text-verified"
          style={{ background: "color-mix(in srgb, var(--prov-state-verified) 18%, transparent)" }}
        >
          Verified plume
        </span>
        <span className="font-mono text-micro text-text-tertiary">Code: ENV-PLUME-PASS</span>
      </div>
    </div>
  );
}
