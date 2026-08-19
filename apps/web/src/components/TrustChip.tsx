import { renderReasonSentence, sortCodesBySeverity } from "../api/reason-codes";
import { formatTrust } from "../lib/format";
import { trustBandDescription, trustState, trustStateLabel } from "../lib/trust";
import { StateGlyph } from "./StateGlyph";

/**
 * A trust score and the reason it is that number.
 *
 * Standing rule 9: a trust score never renders without at least one reason code.
 * That rule is expressed here in the *type* - `reasonCodes` is a non-empty tuple,
 * so omitting it or passing `[]` does not compile - and again at runtime, because
 * data arriving from a future backend cannot be type-checked. A chip asked to
 * render a bare number throws rather than showing one.
 *
 * This is not defensive coding for its own sake. A number on a screen looks exactly
 * the same whether it is true or broken; the reason code is the entire difference
 * between a trust layer and a black box that says "trust me".
 */

/** At least one element, enforced at compile time. */
export type NonEmpty<T> = readonly [T, ...T[]];

export class MissingReasonCodeError extends Error {
  constructor(context: string) {
    super(
      `Refusing to render a trust score for ${context} without a reason code. ` +
        "A trust score always carries its explanation (standing rule 9).",
    );
    this.name = "MissingReasonCodeError";
  }
}

export interface TrustChipProps {
  trust: number | null;
  /** Required and non-empty. This is the rule, not a convenience. */
  reasonCodes: NonEmpty<string>;
  /** Evidence used to fill the reason-code sentence placeholders. */
  evidence?: Record<string, unknown>;
  stationId?: string;
  size?: "sm" | "md";
  /** Suppresses the leading label when the surrounding chrome already says "Trust". */
  hideLabel?: boolean;
  className?: string;
}

export function TrustChip({
  trust,
  reasonCodes,
  evidence,
  stationId,
  size = "md",
  hideLabel = false,
  className,
}: TrustChipProps) {
  if (!reasonCodes || reasonCodes.length === 0) {
    throw new MissingReasonCodeError(stationId ? `station ${stationId}` : "this station");
  }

  const state = trustState(trust);
  const stateLabel = trustStateLabel(state);
  const [primary] = sortCodesBySeverity([...reasonCodes]);
  const primarySentence = primary ? renderReasonSentence(primary, evidence) : "";
  const scoreText = formatTrust(trust);

  const accessibleName = [
    stationId ? `${stationId} trust` : "Trust",
    scoreText,
    stateLabel,
    primarySentence,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-md border border-border bg-bg-raised",
        size === "sm" ? "px-2 text-caption" : "px-3 text-body",
        `prov-state-${state}`,
        className ?? "",
      ].join(" ")}
      data-testid="trust-chip"
      data-state={state}
      title={`${stateLabel}. ${trustBandDescription(state)}`}
    >
      <StateGlyph state={state} size={size === "sm" ? 10 : 12} decorative />
      {!hideLabel && (
        <span className="text-text-tertiary" aria-hidden="true">
          Trust
        </span>
      )}
      <span className="prov-numeric font-mono text-text" data-testid="trust-value">
        {scoreText}
      </span>
      <span className="sr-only">{accessibleName}</span>
      <span aria-hidden="true" className="text-caption">
        {stateLabel}
      </span>
    </span>
  );
}
