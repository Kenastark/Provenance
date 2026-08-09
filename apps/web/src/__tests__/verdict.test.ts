import { describe, expect, it } from "vitest";
import { verdictMeta } from "../lib/verdict";

describe("verdictMeta", () => {
  it("maps the three backend verdicts to labelled, toned states", () => {
    expect(verdictMeta("GENUINE_EVENT")).toMatchObject({ kind: "genuine", tone: "verified" });
    expect(verdictMeta("LIKELY_FAULT")).toMatchObject({ kind: "fault", tone: "fault" });
    expect(verdictMeta("AMBIGUOUS")).toMatchObject({
      kind: "ambiguous",
      tone: "degraded",
      routesToReview: true,
    });
  });

  it("treats a null verdict as pending, never inventing one", () => {
    const meta = verdictMeta(null);
    expect(meta.kind).toBe("pending");
    expect(meta.present).toBe(false);
    expect(meta.label).toBe("pending adjudication");
  });

  it("passes an unrecognised verdict string through verbatim", () => {
    const meta = verdictMeta("sensor fault");
    expect(meta.kind).toBe("other");
    expect(meta.label).toBe("sensor fault");
    expect(meta.present).toBe(true);
  });

  it("only routes ambiguous to review", () => {
    expect(verdictMeta("GENUINE_EVENT").routesToReview).toBe(false);
    expect(verdictMeta("LIKELY_FAULT").routesToReview).toBe(false);
    expect(verdictMeta("AMBIGUOUS").routesToReview).toBe(true);
  });
});
