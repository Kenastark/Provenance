import { STATE_SHAPES, TRUST_FAULT_BELOW, TRUST_VERIFIED_AT } from "../api/tokens.generated";

/**
 * Classifying a trust score into the state an operator reads off the map.
 *
 * The two thresholds are not written here. They are parsed out of
 * design/tokens/tokens.css by scripts/gen_frontend_contract.py, because the marker
 * colour and this classification have to be the same decision - a second copy in
 * TypeScript is exactly how they drift apart, and the drift shows up as a green
 * marker on a station the table calls degraded.
 *
 * Colour is never the only channel: every state carries a shape token too, so the
 * map reads correctly for a colourblind operator and in a greyscale screenshot.
 */

export type TrustState = "verified" | "degraded" | "fault" | "unknown";

export const TRUST_THRESHOLDS = {
  verifiedAt: TRUST_VERIFIED_AT,
  faultBelow: TRUST_FAULT_BELOW,
} as const;

/**
 * `null` trust is `unknown`, not zero. A station with no score yet has not been
 * judged; rendering that as a red fault would be a lie about the data.
 */
export function trustState(trust: number | null | undefined): TrustState {
  if (trust === null || trust === undefined || Number.isNaN(trust)) return "unknown";
  if (trust > TRUST_VERIFIED_AT) return "verified";
  if (trust < TRUST_FAULT_BELOW) return "fault";
  return "degraded";
}

const STATE_LABELS: Record<TrustState, string> = {
  verified: "Verified",
  degraded: "Anomaly",
  fault: "Fault",
  unknown: "Not scored",
};

export function trustStateLabel(state: TrustState): string {
  return STATE_LABELS[state];
}

const STATE_SHAPE: Record<TrustState, string> = {
  verified: STATE_SHAPES.verified,
  degraded: STATE_SHAPES.degraded,
  fault: STATE_SHAPES.fault,
  unknown: STATE_SHAPES.noCoverage,
};

/** The shape token for a state, so colour is never carrying the meaning alone. */
export function trustStateShape(state: TrustState): string {
  return STATE_SHAPE[state];
}

/**
 * The band description shown next to a score, spelled out with the live
 * thresholds so the operator can see the rule rather than trust the colour.
 */
export function trustBandDescription(state: TrustState): string {
  switch (state) {
    case "verified":
      return `Above ${TRUST_VERIFIED_AT} - consistent with its own history and its neighbours.`;
    case "degraded":
      return `Between ${TRUST_FAULT_BELOW} and ${TRUST_VERIFIED_AT} - anomalous or ambiguous; read the reason codes.`;
    case "fault":
      return `Below ${TRUST_FAULT_BELOW} - treat readings from this station as unreliable.`;
    case "unknown":
      return "No trust score has been computed for this station yet.";
  }
}
