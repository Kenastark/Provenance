import { describe, expect, it } from "vitest";
import { parseNotApplicable } from "../lib/adjudication";
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

  it("distinguishes 'not adjudicated yet' from 'considered, does not apply'", () => {
    // Both have a null verdict. Only one of them should tell the operator to go and run
    // a command - the other has already been settled and has a recorded reason.
    const pending = verdictMeta(null, null);
    const notApplicable = verdictMeta(null, { reason: "no rise to propagate" });

    expect(pending.kind).toBe("pending");
    expect(notApplicable.kind).toBe("not_applicable");
    expect(notApplicable.label).not.toContain("pending");
    // Never folded into AMBIGUOUS: we are not unsure, so it must not route to review.
    expect(notApplicable.routesToReview).toBe(false);
    expect(notApplicable.raw).toBeNull();
  });

  it("lets a real verdict win over a stale non-applicability record", () => {
    const meta = verdictMeta("LIKELY_FAULT", { reason: "stale" });
    expect(meta.kind).toBe("fault");
  });
});

describe("parseNotApplicable", () => {
  it("reads the backend's recorded reason off the evidence blob", () => {
    const view = parseNotApplicable({
      adjudication_not_applicable: {
        basis: "no_reading_at_event_time",
        reason: "There is no reading at this timestamp, so there is no rise to carry.",
      },
    });
    expect(view?.basis).toBe("no_reading_at_event_time");
    expect(view?.reason).toContain("no rise");
  });

  it("returns null for a missing, malformed, or reasonless record", () => {
    expect(parseNotApplicable(undefined)).toBeNull();
    expect(parseNotApplicable({})).toBeNull();
    expect(parseNotApplicable({ adjudication_not_applicable: "nope" })).toBeNull();
    expect(parseNotApplicable({ adjudication_not_applicable: { basis: "x" } })).toBeNull();
  });
});
