import type { TrustComponent } from "../api/client";
import { formatTrust } from "../lib/format";

/**
 * The component breakdown that has to sit beside every score.
 *
 * The API cannot serialise a trust score without `components` and `reason_codes`
 * (they are non-empty by construction in the pydantic model). This is the other
 * half of that guarantee: the UI renders the decomposition, so an operator can see
 * which term moved the number rather than being handed a total.
 *
 * `is_placeholder` is surfaced, loudly. Imputation uncertainty is a stand-in until
 * the phase-5 model lands, and a placeholder that looks like a measurement is worse
 * than no term at all.
 */

export interface TrustBreakdownProps {
  components: readonly TrustComponent[];
  className?: string;
}

/**
 * The engine's component names, said the way an operator would say them.
 *
 * Keys are the exact names emitted by src/provenance/trust/components.py. An
 * unknown name is de-camel-cased rather than dropped, so a component added by a
 * later phase still renders with a readable label instead of disappearing.
 */
const PRETTY_NAME: Record<string, string> = {
  HealthConf: "Sensor health",
  ImputationCertainty: "Imputation uncertainty",
  CrossSensorConsistency: "Cross-sensor consistency",
  PhysicalPlausibility: "Physical plausibility",
};

/** `evidence.pct` / `evidence.modelled_pct` are numbers keyed loosely (see schemas.py). */
function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * The ImputationCertainty row's two figures, each labelled so a reader never mistakes
 * one for the other: the raw fraction of the window that is absent (always present),
 * and the trained model's calibrated uncertainty for this station/window (only once a
 * model covers it - see `provenance.models.hstgat.imputation_serving`).
 */
function imputationLines(component: TrustComponent): string[] {
  if (component.name !== "ImputationCertainty") return [];
  const pct = asNumber(component.evidence?.pct);
  const modelledPct = asNumber(component.evidence?.modelled_pct);
  const lines: string[] = [];
  if (pct !== null) lines.push(`Absent in window: ${pct}%`);
  if (modelledPct !== null) {
    lines.push(`Imputation uncertainty (modelled): ${(modelledPct / 100).toFixed(2)}`);
  }
  return lines;
}

function prettyName(name: string): string {
  const known = PRETTY_NAME[name];
  if (known) return known;
  return name
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/^./, (character) => character.toUpperCase());
}

export function TrustBreakdown({ components, className }: TrustBreakdownProps) {
  if (components.length === 0) {
    // Unreachable through the API, which validates non-empty. Kept because a
    // silent empty list here would be a trust score without its breakdown.
    return (
      <p
        className={["text-body prov-state-fault", className ?? ""].join(" ")}
        data-testid="trust-breakdown-missing"
      >
        This score arrived without its component breakdown and cannot be shown.
      </p>
    );
  }

  return (
    <table className={["prov-table", className ?? ""].join(" ")} data-testid="trust-breakdown">
      <caption className="sr-only">Trust score component breakdown</caption>
      <thead>
        <tr>
          <th scope="col" className="py-2">
            Component
          </th>
          <th scope="col" className="py-2 text-right">
            Value
          </th>
          <th scope="col" className="py-2 text-right">
            Weight
          </th>
          <th scope="col" className="py-2 text-right">
            Contribution
          </th>
        </tr>
      </thead>
      <tbody>
        {components.map((component) => (
          <tr key={component.name} data-testid={`trust-component-${component.name}`}>
            <th scope="row" className="py-2 pr-3 text-left font-normal text-text">
              <span className="flex flex-col">
                <span>
                  {prettyName(component.name)}
                  {component.is_placeholder && (
                    <span
                      className="ml-2 rounded-sm border border-border px-1 text-micro prov-state-degraded"
                      data-testid="placeholder-marker"
                    >
                      placeholder
                    </span>
                  )}
                </span>
                {imputationLines(component).length > 0 ? (
                  <span
                    className="flex flex-col text-caption text-text-tertiary"
                    data-testid="imputation-uncertainty-lines"
                  >
                    {imputationLines(component).map((line) => (
                      <span key={line}>{line}</span>
                    ))}
                  </span>
                ) : (
                  component.detail && (
                    <span className="text-caption text-text-tertiary">{component.detail}</span>
                  )
                )}
              </span>
            </th>
            <td className="prov-numeric py-2 text-right font-mono">
              {formatTrust(component.value)}
            </td>
            <td className="prov-numeric py-2 text-right font-mono text-text-secondary">
              {formatTrust(component.weight)}
            </td>
            <td className="prov-numeric py-2 text-right font-mono">
              {formatTrust(component.contribution)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
