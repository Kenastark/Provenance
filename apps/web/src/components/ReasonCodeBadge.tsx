import { reasonCode, renderReasonSentenceParts, severityTone } from "../api/reason-codes";

/**
 * One reason code, said in English.
 *
 * The code itself ("R09") is shown because it is the key into the audit trail and
 * the export, but it is never the whole label - the sentence beside it is what an
 * operator actually acts on. `variant="code"` is for dense table cells where the
 * sentence lives in a tooltip and an adjacent column; `variant="sentence"` is the
 * full statement used in the station detail and evidence panels.
 *
 * Coverage codes are visually distinct on purpose. "This station does not carry a
 * wind sensor" is a fact about the network, not a defect, and must never read as a
 * fault - counting those toward the defect rate is the single easiest way to
 * inflate the most scrutinised number in the pitch.
 */

export interface ReasonCodeBadgeProps {
  code: string;
  evidence?: Record<string, unknown>;
  variant?: "code" | "sentence";
  /**
   * Supporting prose from the payload, shown when the sentence could not be fully
   * substituted. The trust codes need it: the engine's numbers reach the API as
   * `components[].detail` rather than as an evidence dict.
   */
  detail?: string | null;
  className?: string;
}

const TONE_CLASS: Record<string, string> = {
  fault: "prov-state-fault",
  degraded: "prov-state-degraded",
  neutral: "prov-state-unknown",
};

export function ReasonCodeBadge({
  code,
  evidence,
  variant = "sentence",
  detail,
  className,
}: ReasonCodeBadgeProps) {
  const def = reasonCode(code);
  const { text: sentence, complete } = renderReasonSentenceParts(code, evidence);
  const isCoverage = def?.category === "coverage";
  const tone = isCoverage ? "neutral" : severityTone(code);
  const showDetail = Boolean(detail) && !complete;

  if (variant === "code") {
    return (
      <span
        className={["inline-flex items-center gap-1 font-mono text-caption", className ?? ""].join(
          " ",
        )}
        data-testid="reason-code-badge"
        data-code={code}
        data-category={def?.category ?? "unknown"}
        title={sentence}
      >
        <span
          aria-hidden="true"
          className={[
            "rounded-sm border border-border px-1",
            TONE_CLASS[tone] ?? TONE_CLASS.neutral,
          ].join(" ")}
        >
          {code}
        </span>
        <span className="sr-only">{`${code}: ${sentence}`}</span>
      </span>
    );
  }

  return (
    <span
      className={["flex items-start gap-2 text-body", className ?? ""].join(" ")}
      data-testid="reason-code-badge"
      data-code={code}
      data-category={def?.category ?? "unknown"}
    >
      <span
        aria-hidden="true"
        className={[
          "mt-1 shrink-0 rounded-sm border border-border px-1 font-mono text-micro",
          TONE_CLASS[tone] ?? TONE_CLASS.neutral,
        ].join(" ")}
      >
        {code}
      </span>
      <span className="text-text-secondary">
        <span className="sr-only">{`${code}. `}</span>
        {sentence}
        {isCoverage && (
          <span className="ml-2 text-caption text-text-tertiary">
            Coverage fact — excluded from the defect rate.
          </span>
        )}
        {showDetail && (
          <span className="block text-caption text-text-tertiary" data-testid="reason-code-detail">
            {detail}
          </span>
        )}
      </span>
    </span>
  );
}
