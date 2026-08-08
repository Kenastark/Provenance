import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReasonCodeBadge } from "../components/ReasonCodeBadge";
import {
  countsTowardDefectRate,
  renderReasonSentence,
  renderReasonSentenceParts,
  sortCodesBySeverity,
} from "../api/reason-codes";

describe("reason-code rendering", () => {
  it("substitutes the detector's evidence into the operator sentence", () => {
    expect(renderReasonSentence("R09", { pm25: 41.2, pm10: 38 })).toBe(
      "PM2.5 (41.2) exceeds PM10 (38), which is physically impossible.",
    );
  });

  it("returns the raw template when evidence is missing, matching the Python renderer", () => {
    // ReasonCode.render() in src/provenance/config/reason_codes.py does exactly this,
    // so the CLI, the HTML report and the dashboard never word a defect differently.
    expect(renderReasonSentence("R02", {})).toBe(
      "No readings for {duration} - the station stopped transmitting.",
    );
  });

  it("marks partial substitution rather than showing a raw placeholder", () => {
    const { text, complete } = renderReasonSentenceParts("R02", {});
    expect(complete).toBe(false);
    expect(text).toBe("No readings for — - the station stopped transmitting.");
    expect(text).not.toMatch(/[{}]/);
  });

  it("says so, instead of throwing, for a code it does not know", () => {
    expect(renderReasonSentence("R99")).toMatch(/Unrecognised reason code R99/);
  });

  it("knows which codes stay out of the defect rate", () => {
    expect(countsTowardDefectRate("R07")).toBe(true);
    expect(countsTowardDefectRate("R18")).toBe(false); // structural absence
    expect(countsTowardDefectRate("R19")).toBe(false); // absent source
    expect(countsTowardDefectRate("T01")).toBe(false); // trust explanation
  });

  it("orders codes most severe first", () => {
    expect(sortCodesBySeverity(["R01", "R07", "R14"])).toEqual(["R07", "R14", "R01"]);
  });
});

describe("ReasonCodeBadge", () => {
  it("shows the code and the sentence", () => {
    render(<ReasonCodeBadge code="R07" evidence={{ value: 3000, unit: "µg/m3", parameter: "PM10" }} />);
    expect(screen.getByTestId("reason-code-badge")).toHaveAttribute("data-code", "R07");
    expect(
      screen.getByText(/Value of 3000 µg\/m3 exceeds the physical maximum for PM10\./),
    ).toBeInTheDocument();
  });

  it("marks a coverage code as excluded from the defect rate", () => {
    render(<ReasonCodeBadge code="R18" evidence={{ parameter: "Wind_Speed" }} />);
    expect(screen.getByTestId("reason-code-badge")).toHaveAttribute("data-category", "coverage");
    expect(screen.getByText(/excluded from the defect rate/i)).toBeInTheDocument();
  });

  it("falls back to the component detail when the sentence cannot be completed", () => {
    render(<ReasonCodeBadge code="T02" detail="imputation uncertainty 12.0% (placeholder, no model)" />);
    expect(screen.getByTestId("reason-code-detail")).toHaveTextContent("12.0%");
  });

  it("hides the detail when the sentence already carries the numbers", () => {
    render(<ReasonCodeBadge code="T01" evidence={{ n_defects: 7 }} detail="7 active flags" />);
    expect(screen.getByText(/reduced by 7 active defect\(s\)/i)).toBeInTheDocument();
    expect(screen.queryByTestId("reason-code-detail")).not.toBeInTheDocument();
  });

  it("keeps the sentence available to screen readers in the dense code variant", () => {
    render(<ReasonCodeBadge code="R12" variant="code" evidence={{ duration: "336 h" }} />);
    expect(
      screen.getByText("R12: Reading has not changed for 336 h - likely a frozen sensor."),
    ).toBeInTheDocument();
  });
});
