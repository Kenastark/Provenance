import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProvEvent } from "../../api/client";
import type { AdjudicationView } from "../../lib/adjudication";
import { formatTimestamp } from "../../lib/format";
import { verdictMeta } from "../../lib/verdict";

/**
 * The event detail: the adjudicator's argument, laid out for a human to check.
 *
 * The verdict and its confidence, the expected-vs-actual downwind series overlaid,
 * the downwind neighbours it weighed, and the covariates it could not yet consult.
 * AMBIGUOUS is drawn as a routed-to-review state, never dressed up as a confident
 * call — the same guarantee the value object enforces on the backend.
 */

const TONE_CLASS = {
  verified: "prov-state-verified",
  degraded: "prov-state-degraded",
  fault: "prov-state-fault",
  unknown: "prov-state-unknown",
} as const;

export function AdjudicationDetail({
  event,
  adjudication,
}: {
  event: ProvEvent;
  adjudication: AdjudicationView;
}) {
  const meta = verdictMeta(adjudication.verdict);
  const wind = adjudication.wind;

  const chartData = adjudication.series.timestamps.map((t, i) => ({
    label: formatTimestamp(t),
    expected: adjudication.series.expected[i] ?? null,
    actual: adjudication.series.actual[i] ?? null,
  }));

  return (
    <section
      className="flex flex-col gap-4"
      aria-label={`Adjudication for event ${event.id}`}
      data-testid="adjudication-detail"
    >
      {/* -------------------------------------------------- verdict + confidence */}
      <div className="prov-panel p-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <h3 className="text-subhead">
            {event.station_id} · {event.parameter}
          </h3>
          <span
            className={`rounded-sm border border-current px-2 text-caption ${TONE_CLASS[meta.tone]}`}
            data-testid="adjudication-verdict"
            data-verdict={adjudication.verdict}
          >
            {meta.label}
          </span>
          <span className="prov-numeric font-mono text-caption text-text-secondary">
            confidence {(adjudication.confidence * 100).toFixed(0)}% ({adjudication.confidenceBand})
          </span>
        </div>
        <p className="mt-1 text-caption text-text-tertiary">
          Match score {(adjudication.matchScore * 100).toFixed(0)}% across {adjudication.nUsable} of{" "}
          {adjudication.nDownwind} downwind neighbour{adjudication.nDownwind === 1 ? "" : "s"}.
        </p>
        {meta.routesToReview && (
          <p
            className="mt-2 rounded-sm p-2 text-caption prov-state-degraded"
            role="status"
            data-testid="adjudication-review"
          >
            Routed to human review — the evidence does not settle this either way. This is a
            designed outcome, not a failure.
          </p>
        )}
        {wind.provenance && wind.provenance !== "unavailable" ? (
          <p className="mt-2 text-caption text-text-tertiary" data-testid="adjudication-wind">
            Wind from {wind.fromDeg ?? "—"}°{wind.speed !== null ? ` at ${wind.speed} ${wind.speedUnit}` : ""} ·
            provenance {wind.provenance}
          </p>
        ) : (
          <p className="mt-2 text-caption text-text-tertiary" data-testid="adjudication-wind">
            No wind vector at the event hour — propagation could not be assessed.
          </p>
        )}
      </div>

      {/* ------------------------------------------ expected vs actual series */}
      <div className="prov-panel p-4">
        <h4 className="mb-2 text-subhead">Expected vs actual downwind rise</h4>
        {chartData.length <= 1 ? (
          <p className="text-caption text-text-tertiary">
            No downwind series to draw — there were no usable neighbours to compare against.
          </p>
        ) : (
          <div style={{ width: "100%", height: 220 }} data-testid="adjudication-chart">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--prov-chart-grid)" strokeDasharray="2 4" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
                  stroke="var(--prov-chart-grid)"
                  minTickGap={32}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--prov-text-tertiary)" }}
                  stroke="var(--prov-chart-grid)"
                  width={56}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--prov-surface)",
                    border: "1px solid var(--prov-border)",
                    borderRadius: "var(--prov-radius-md)",
                    fontSize: "var(--prov-size-caption)",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "var(--prov-size-caption)" }} />
                <Line
                  name="Expected"
                  type="monotone"
                  dataKey="expected"
                  stroke="var(--prov-chart-series-1)"
                  strokeDasharray="4 3"
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  name="Actual"
                  type="monotone"
                  dataKey="actual"
                  stroke="var(--prov-chart-series-2)"
                  dot={{ r: 2 }}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ---------------------------------------------------- downwind neighbours */}
      <div className="prov-panel p-4">
        <h4 className="mb-2 text-subhead">Downwind neighbours weighed</h4>
        {adjudication.neighbours.length === 0 ? (
          <p className="text-caption text-text-tertiary">
            No neighbour sat downwind of this event under the current wind.
          </p>
        ) : (
          <table className="w-full text-caption" data-testid="adjudication-neighbours">
            <thead>
              <tr className="text-left text-text-tertiary">
                <th className="font-normal">Station</th>
                <th className="font-normal">Dist (km)</th>
                <th className="font-normal">Weight</th>
                <th className="font-normal">Expected</th>
                <th className="font-normal">Actual</th>
                <th className="font-normal">Corroborated</th>
              </tr>
            </thead>
            <tbody className="prov-numeric font-mono">
              {adjudication.neighbours.map((n) => (
                <tr key={n.stationId} data-testid="adjudication-neighbour" data-station={n.stationId}>
                  <td>{n.stationId}</td>
                  <td>{n.distanceKm.toFixed(2)}</td>
                  <td>{n.edgeWeight.toFixed(3)}</td>
                  <td>{n.expectedExcess.toFixed(1)}</td>
                  <td>{n.actualExcess === null ? "—" : n.actualExcess.toFixed(1)}</td>
                  <td className={n.corroborated ? "prov-state-verified" : "prov-state-fault"}>
                    {n.corroborated ? "yes" : "no"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ------------------------------------------------------- covariate stubs */}
      <div className="prov-panel p-4">
        <h4 className="mb-2 text-subhead">Covariates</h4>
        <ul className="m-0 list-none space-y-2 p-0" data-testid="adjudication-covariates">
          {adjudication.covariates.map((c) => (
            <li key={c.name} className="text-caption">
              <span className="font-mono text-text">{c.name}</span>:{" "}
              <span className="text-text-secondary">{c.state}</span>
              <span className="block text-text-tertiary">{c.reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
