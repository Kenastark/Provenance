import type { TrustState } from "./trust";

/**
 * The adjudicator's verdict, mapped to something the operator screens can render.
 *
 * The three backend verdicts are GENUINE_EVENT / LIKELY_FAULT / AMBIGUOUS. AMBIGUOUS
 * is a first-class outcome, not a failure — it means the plume could not be settled
 * either way and a human should look. Any other (or missing) string is passed
 * through untouched: the dashboard never invents or normalises a verdict it did not
 * get from the backend, and a null one still reads as "pending adjudication".
 */

export type VerdictKind = "genuine" | "fault" | "ambiguous" | "pending" | "other";

export interface VerdictMeta {
  kind: VerdictKind;
  /** The operator-facing label. For an unknown verdict this is the raw string. */
  label: string;
  /** Reuses the trust state palette so green/amber/red carry their usual meaning. */
  tone: TrustState;
  present: boolean;
  routesToReview: boolean;
  raw: string | null;
}

export function verdictMeta(verdict: string | null | undefined): VerdictMeta {
  if (!verdict) {
    return {
      kind: "pending",
      label: "pending adjudication",
      tone: "unknown",
      present: false,
      routesToReview: false,
      raw: null,
    };
  }
  switch (verdict) {
    case "GENUINE_EVENT":
      return {
        kind: "genuine",
        label: "Genuine plume",
        tone: "verified",
        present: true,
        routesToReview: false,
        raw: verdict,
      };
    case "LIKELY_FAULT":
      return {
        kind: "fault",
        label: "Likely fault",
        tone: "fault",
        present: true,
        routesToReview: false,
        raw: verdict,
      };
    case "AMBIGUOUS":
      return {
        kind: "ambiguous",
        label: "Ambiguous — review",
        tone: "degraded",
        present: true,
        routesToReview: true,
        raw: verdict,
      };
    default:
      // A verdict string the client does not recognise is shown verbatim rather than
      // guessed at — the same discipline the null case follows.
      return {
        kind: "other",
        label: verdict,
        tone: "unknown",
        present: true,
        routesToReview: false,
        raw: verdict,
      };
  }
}
