import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MissingReasonCodeError, TrustChip, type NonEmpty } from "../components/TrustChip";
import { TRUST_THRESHOLDS } from "../lib/trust";

/**
 * Standing rule 9, tested from both ends.
 *
 * The compile-time half is `reasonCodes: NonEmpty<string>` - omitting it or passing
 * `[]` is a type error, which these tests assert with @ts-expect-error. The runtime
 * half is the throw, which is what protects against data that TypeScript never saw.
 */

const codes = ["T01", "T04"] as NonEmpty<string>;

describe("TrustChip", () => {
  it("renders the score with its state", () => {
    render(<TrustChip trust={0.51} reasonCodes={codes} stationId="STA-01" />);
    expect(screen.getByTestId("trust-value")).toHaveTextContent("0.51");
    expect(screen.getByTestId("trust-chip")).toHaveAttribute("data-state", "degraded");
  });

  it("cannot render without a reason code prop", () => {
    // The prop is required: leaving it out does not compile.
    // @ts-expect-error reasonCodes is required — this is the compile-time half of rule 9.
    expect(() => render(<TrustChip trust={0.9} />)).toThrow(MissingReasonCodeError);
  });

  it("cannot render with an empty reason code list", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() =>
      // @ts-expect-error an empty array is not NonEmpty<string> — also a compile-time error.
      render(<TrustChip trust={0.9} reasonCodes={[]} stationId="STA-09" />),
    ).toThrow(/without a reason code/i);
    spy.mockRestore();
  });

  it("names the station and the primary reason in its accessible text", () => {
    render(<TrustChip trust={0.22} reasonCodes={["T04"] as NonEmpty<string>} stationId="STA-03" />);
    expect(
      screen.getByText(/STA-03 trust, 0\.22, Fault, Trust is reduced by readings near or beyond/i),
    ).toBeInTheDocument();
  });

  it("classifies against the thresholds from the design tokens", () => {
    const { rerender } = render(
      <TrustChip trust={TRUST_THRESHOLDS.verifiedAt + 0.01} reasonCodes={codes} />,
    );
    expect(screen.getByTestId("trust-chip")).toHaveAttribute("data-state", "verified");

    // Exactly on the boundary is the anomaly band, matching "amber 0.5-0.85".
    rerender(<TrustChip trust={TRUST_THRESHOLDS.verifiedAt} reasonCodes={codes} />);
    expect(screen.getByTestId("trust-chip")).toHaveAttribute("data-state", "degraded");

    rerender(<TrustChip trust={TRUST_THRESHOLDS.faultBelow} reasonCodes={codes} />);
    expect(screen.getByTestId("trust-chip")).toHaveAttribute("data-state", "degraded");

    rerender(<TrustChip trust={TRUST_THRESHOLDS.faultBelow - 0.01} reasonCodes={codes} />);
    expect(screen.getByTestId("trust-chip")).toHaveAttribute("data-state", "fault");
  });

  it("shows an unscored station as unknown rather than as a fault", () => {
    render(<TrustChip trust={null} reasonCodes={codes} />);
    const chip = screen.getByTestId("trust-chip");
    expect(chip).toHaveAttribute("data-state", "unknown");
    expect(screen.getByTestId("trust-value")).toHaveTextContent("—");
  });

  it("carries a shape as well as a colour, so colour is never the only channel", () => {
    const { rerender } = render(<TrustChip trust={0.95} reasonCodes={codes} />);
    const shapeOf = () => screen.getByTestId("trust-chip").querySelector("svg")?.dataset.shape;
    const verified = shapeOf();

    rerender(<TrustChip trust={0.2} reasonCodes={codes} />);
    const fault = shapeOf();

    expect(verified).toBeTruthy();
    expect(fault).toBeTruthy();
    expect(verified).not.toEqual(fault);
  });
});
