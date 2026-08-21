import { describe, expect, it } from "vitest";
import { parseInfraMetrics, sumMetric } from "../features/admin/infraMetrics";

const SAMPLE = `
# HELP prov_up Whether the service is up
# TYPE prov_up gauge
prov_up 1
# HELP prov_http_requests_total Total requests
# TYPE prov_http_requests_total counter
prov_http_requests_total{method="GET",path="/v1/stations",status="200"} 42
prov_http_requests_total{method="POST",path="/v1/decision/dispatch",status="200"} 3
# HELP prov_http_requests_in_flight In-flight requests
# TYPE prov_http_requests_in_flight gauge
prov_http_requests_in_flight 2
`;

describe("sumMetric", () => {
  it("reads an unlabelled gauge", () => {
    expect(sumMetric(SAMPLE, "prov_up")).toBe(1);
  });

  it("sums a counter across every label combination", () => {
    expect(sumMetric(SAMPLE, "prov_http_requests_total")).toBe(45);
  });

  it("returns null for a series that is not present", () => {
    expect(sumMetric(SAMPLE, "prov_nonexistent_metric")).toBeNull();
  });
});

describe("parseInfraMetrics", () => {
  it("reports the service up and the headline request counts", () => {
    expect(parseInfraMetrics(SAMPLE)).toEqual({
      up: true,
      requestsTotal: 45,
      requestsInFlight: 2,
    });
  });

  it("reports down rather than crashing when prov_up is 0", () => {
    expect(parseInfraMetrics("prov_up 0\n").up).toBe(false);
  });

  it("reports unknown, not down, when the series is absent entirely", () => {
    expect(parseInfraMetrics("").up).toBeNull();
  });
});
