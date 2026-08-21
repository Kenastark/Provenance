import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useApiClient } from "../../api/queries";

/**
 * The infra plane of the two-plane monitor.
 *
 * `/metrics` is a Prometheus scrape target (`api/metrics.py`) - plain-text
 * exposition format, top-level, unauthenticated, deliberately not JSON and not
 * under `/v1`. A real deployment points Prometheus/Grafana at it directly; this
 * reads the same three headline series so the admin screen has an honest "is the
 * service up" tile without asking an operator to open a second tool for it. It is
 * a small, tolerant parser of a handful of named series, not a Prometheus client -
 * anything more than that belongs in Grafana, not hand-rolled here.
 */

export interface InfraMetrics {
  up: boolean | null;
  requestsTotal: number | null;
  requestsInFlight: number | null;
}

/** Sums every series matching `name`, label sets and all - a counter is exposed as
 * one line per label combination, and the headline figure is their total. */
export function sumMetric(text: string, name: string): number | null {
  const pattern = new RegExp(`^${name}(?:\\{[^}]*\\})?\\s+([0-9eE+.-]+)\\s*$`, "gm");
  let total: number | null = null;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    const value = Number(match[1]);
    if (Number.isFinite(value)) total = (total ?? 0) + value;
  }
  return total;
}

export function parseInfraMetrics(text: string): InfraMetrics {
  const up = sumMetric(text, "prov_up");
  return {
    up: up === null ? null : up > 0,
    requestsTotal: sumMetric(text, "prov_http_requests_total"),
    requestsInFlight: sumMetric(text, "prov_http_requests_in_flight"),
  };
}

export function useInfraMetrics(): UseQueryResult<InfraMetrics> {
  const client = useApiClient();
  return useQuery({
    queryKey: ["admin", "infra-metrics"],
    queryFn: async ({ signal }) => {
      const response = await fetch(`${client.config.baseUrl}/metrics`, { signal });
      if (!response.ok) {
        throw new Error(`The metrics endpoint returned ${response.status}.`);
      }
      return parseInfraMetrics(await response.text());
    },
  });
}
