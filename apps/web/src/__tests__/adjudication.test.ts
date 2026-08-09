import { describe, expect, it } from "vitest";
import { parseAdjudication } from "../lib/adjudication";

const BUNDLE = {
  adjudication: {
    verdict: "GENUINE_EVENT",
    confidence: 1.0,
    confidence_band: "high",
    routes_to_review: false,
    evidence: {
      wind: { from_deg: 270, to_deg: 90, speed: 5, speed_unit: "m/s", provenance: "station-local" },
      downwind_neighbours: [
        {
          station_id: "N1",
          distance_km: 3,
          bearing_deg: 90,
          edge_weight: 0.39,
          wind_provenance: "station-local",
          carries_parameter: true,
          arrival_delay_min: 10,
          expected_excess: 93,
          actual_excess: 93,
          corroborated: true,
        },
      ],
      series: { timestamps: ["t0", "t1"], expected: [0, 93], actual: [0, 93] },
      match_score: 1.0,
      n_downwind: 2,
      n_usable: 2,
      covariates: [{ name: "traffic", state: "unavailable", reason: "Enclod unconfirmed" }],
      reason_codes: ["R22"],
      notes: ["No headline accuracy figure is reported."],
    },
  },
};

describe("parseAdjudication", () => {
  it("returns null when there is no adjudication bundle", () => {
    expect(parseAdjudication(undefined)).toBeNull();
    expect(parseAdjudication({ value: 3000 })).toBeNull();
    expect(parseAdjudication({ adjudication: {} })).toBeNull();
  });

  it("parses a full bundle into a typed view", () => {
    const view = parseAdjudication(BUNDLE);
    expect(view).not.toBeNull();
    expect(view!.verdict).toBe("GENUINE_EVENT");
    expect(view!.confidence).toBe(1.0);
    expect(view!.matchScore).toBe(1.0);
    expect(view!.neighbours).toHaveLength(1);
    expect(view!.neighbours[0]).toMatchObject({ stationId: "N1", corroborated: true });
    expect(view!.series.expected).toEqual([0, 93]);
    expect(view!.wind.fromDeg).toBe(270);
    expect(view!.covariates[0]?.name).toBe("traffic");
  });

  it("tolerates a null actual excess without throwing", () => {
    const clone = structuredClone(BUNDLE);
    clone.adjudication.evidence.downwind_neighbours[0]!.actual_excess = null as unknown as number;
    const view = parseAdjudication(clone);
    expect(view!.neighbours[0]!.actualExcess).toBeNull();
  });
});
