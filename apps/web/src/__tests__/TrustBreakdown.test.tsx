import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TrustBreakdown } from "../components/TrustBreakdown";
import { trustComponents, trustComponentsModelled } from "../test/fixtures";

/**
 * The two ImputationCertainty questions - "how much is absent" and "how uncertain
 * is the trained model's reconstruction" - must never collapse into one number
 * wearing two names (U16). The placeholder badge is the other half: it must show
 * only when no model covers the station, never when a modelled figure is present.
 */
describe("TrustBreakdown", () => {
  it("shows the placeholder badge and only the raw absent figure with no model", () => {
    render(<TrustBreakdown components={trustComponents} />);
    const row = screen.getByTestId("trust-component-ImputationCertainty");
    expect(row).toHaveTextContent("Absent in window: 12%");
    expect(row.querySelector('[data-testid="placeholder-marker"]')).toBeInTheDocument();
    expect(row).not.toHaveTextContent("modelled");
  });

  it("shows both figures, separately labelled, and no placeholder badge once modelled", () => {
    render(<TrustBreakdown components={trustComponentsModelled} />);
    const row = screen.getByTestId("trust-component-ImputationCertainty");
    expect(row).toHaveTextContent("Absent in window: 12%");
    expect(row).toHaveTextContent("Imputation uncertainty (modelled): 0.12");
    expect(row.querySelector('[data-testid="placeholder-marker"]')).not.toBeInTheDocument();
  });
});
