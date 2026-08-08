import { REASON_CODES, type ReasonCodeDef, type ReasonCodeSeverity } from "./reason-codes.generated";

export type { ReasonCodeDef, ReasonCodeCategory, ReasonCodeSeverity } from "./reason-codes.generated";
export { REASON_CODES } from "./reason-codes.generated";

/**
 * Turning a reason code into the sentence an operator reads.
 *
 * "72% trust" means nothing to a city official deciding whether to issue a public
 * warning; "PM2.5 (41.2) exceeds PM10 (38.0), which is physically impossible" is
 * the whole product. Every code in the registry carries such a template, and this
 * module fills its placeholders from the detector's evidence.
 *
 * The substitution deliberately mirrors `ReasonCode.render()` in
 * src/provenance/config/reason_codes.py: if any placeholder is missing from the
 * evidence, the *unsubstituted* template is returned rather than a sentence with a
 * hole in it. The CLI, the HTML report, and this dashboard therefore say exactly
 * the same words about the same defect, which is what makes the audit trail worth
 * anything.
 */

const PLACEHOLDER = /\{(\w+)\}/g;

export type Evidence = Record<string, unknown>;

/** Look a code up, or `undefined` if the backend sent one we do not know. */
export function reasonCode(code: string): ReasonCodeDef | undefined {
  return REASON_CODES[code];
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
  }
  return String(value);
}

/**
 * Render a code's operator sentence with evidence substituted.
 *
 * Python-parity: if any placeholder is missing, the raw template comes back. Use
 * this wherever the dashboard must say exactly what the CLI and the HTML report
 * say - defect and event codes, whose detectors always attach a complete evidence
 * dict.
 *
 * An unknown code returns a sentence that says so, rather than throwing: the UI
 * running slightly ahead of or behind the backend registry must still render
 * something truthful, and a blank chip would be worse than an honest one.
 */
export function renderReasonSentence(code: string, evidence: Evidence = {}): string {
  const def = REASON_CODES[code];
  if (!def) return `Unrecognised reason code ${code}.`;
  const { text, complete } = renderReasonSentenceParts(code, evidence);
  return complete ? text : def.sentence;
}

export interface RenderedSentence {
  text: string;
  /** False when at least one placeholder had no evidence to fill it. */
  complete: boolean;
}

/**
 * Substitute what the evidence supplies and mark anything it does not.
 *
 * The trust codes (T01-T05) need this. Their numbers are computed by the trust
 * engine but the API returns them as prose in `notes` and `components[].detail`
 * rather than as a machine-readable evidence dict, so the UI can fill some
 * placeholders and not others. An unfilled slot renders as an em dash and the
 * caller shows the component detail beside it - never a fabricated number, and
 * never a raw `{placeholder}` on an operator's screen.
 */
export function renderReasonSentenceParts(code: string, evidence: Evidence = {}): RenderedSentence {
  const def = REASON_CODES[code];
  if (!def) return { text: `Unrecognised reason code ${code}.`, complete: false };

  let complete = true;
  const text = def.sentence.replace(PLACEHOLDER, (_match, key: string) => {
    const value = evidence[key];
    if (value === undefined || value === null) {
      complete = false;
      return "—";
    }
    return formatValue(value);
  });
  return { text, complete };
}

/** Codes that count toward the headline defect rate. Coverage and trust codes never do. */
export function countsTowardDefectRate(code: string): boolean {
  return REASON_CODES[code]?.countsTowardDefectRate ?? false;
}

const SEVERITY_ORDER: Record<ReasonCodeSeverity, number> = {
  info: 0,
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

export function severityRank(severity: ReasonCodeSeverity | undefined): number {
  return severity ? SEVERITY_ORDER[severity] : -1;
}

/** Most severe first, then by code so the order is stable across renders. */
export function sortCodesBySeverity(codes: readonly string[]): string[] {
  return [...codes].sort((a, b) => {
    const delta = severityRank(REASON_CODES[b]?.severity) - severityRank(REASON_CODES[a]?.severity);
    return delta !== 0 ? delta : a.localeCompare(b);
  });
}

/**
 * Which visual weight a severity gets. Only three states exist in the palette, so
 * this is a deliberate collapse rather than a five-colour scale nobody can read.
 */
export type SeverityTone = "fault" | "degraded" | "neutral";

export function severityTone(code: string): SeverityTone {
  const severity = REASON_CODES[code]?.severity;
  if (severity === "critical" || severity === "high") return "fault";
  if (severity === "medium" || severity === "low") return "degraded";
  return "neutral";
}
