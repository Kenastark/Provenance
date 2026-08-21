import { formatTrust } from "../lib/format";

/**
 * A ranking value and the factors that produced it - never a bare number.
 *
 * `TrustBreakdown` covers `ComponentOut` (weight/contribution). Alert risk and
 * maintenance priority are a parallel but differently-shaped case: the alerts and
 * maintenance routers say explicitly in their own docstrings that a risk or
 * priority score is never shown alone, but their `risk_factors`/priority terms are
 * a flat multiplicand list, not weighted components with a contribution term. This
 * is that shape's renderer, reused for both rather than building one each.
 */

export interface Factor {
  key: string;
  label: string;
  value: number;
}

export interface FactorBreakdownProps {
  value: number;
  valueLabel: string;
  factors: readonly Factor[];
  /** How the factors combine into `value`, said in words next to the number. */
  formula?: string;
  className?: string;
}

export function FactorBreakdown({
  value,
  valueLabel,
  factors,
  formula,
  className,
}: FactorBreakdownProps) {
  return (
    <div className={className} data-testid="factor-breakdown">
      <div className="flex items-baseline gap-2">
        <span className="prov-numeric font-mono text-heading" data-testid="factor-breakdown-value">
          {formatTrust(value)}
        </span>
        <span className="text-caption text-text-tertiary">{valueLabel}</span>
      </div>
      {formula && <p className="mt-1 text-caption text-text-tertiary">{formula}</p>}
      <table className="prov-table mt-2">
        <caption className="sr-only">{valueLabel} factors</caption>
        <thead>
          <tr>
            <th scope="col" className="py-1">
              Factor
            </th>
            <th scope="col" className="py-1 text-right">
              Value
            </th>
          </tr>
        </thead>
        <tbody>
          {factors.map((factor) => (
            <tr key={factor.key} data-testid={`factor-${factor.key}`}>
              <th scope="row" className="py-1 text-left font-normal text-text">
                {factor.label}
              </th>
              <td className="prov-numeric py-1 text-right font-mono">{formatTrust(factor.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
