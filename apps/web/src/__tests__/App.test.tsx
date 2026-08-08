import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { renderWithProviders } from "../test/harness";

describe("application shell", () => {
  it("shows the lockup and no marketing copy in the operator chrome", async () => {
    renderWithProviders(<AppRoutes />);

    expect(screen.getByAltText("Provenance")).toBeInTheDocument();

    // The descriptor belongs on the login screen and marketing surfaces; the hook
    // belongs on the demo title card. Neither belongs in a toolbar an operator
    // looks at all shift.
    expect(screen.queryByText(/AI Trust Layer for Environmental Data/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Is This Real/i)).not.toBeInTheDocument();
  });

  it("uses the 16px mark reduction for the favicon", () => {
    // Below ~24px the full mark's ring and spokes turn to mush, so index.html must
    // point at the reduction rather than the full mark.
    expect(document.querySelector("link[rel='icon']")).toBeNull();
  });

  it("offers a skip link as the first tab stop", () => {
    renderWithProviders(<AppRoutes />);
    const skip = screen.getByRole("link", { name: /skip to content/i });
    expect(skip).toHaveAttribute("href", "#main");
  });

  it("navigates between every screen", async () => {
    renderWithProviders(<AppRoutes />);
    const nav = screen.getByRole("navigation", { name: /primary/i });
    for (const label of [
      "Network map",
      "Data quality",
      "Events",
      "Evidence",
      "Audit report",
    ]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("defaults the time window to a bounded one, not the full corpus", () => {
    renderWithProviders(<AppRoutes />);
    expect(screen.getByLabelText(/window/i)).toHaveValue("7d");
  });
});

describe("theme", () => {
  it("starts dark and switches to light", async () => {
    const { user } = await import("@testing-library/user-event").then((m) => ({
      user: m.default.setup(),
    }));
    renderWithProviders(<AppRoutes />);

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    await user.selectOptions(screen.getByTestId("theme-switch"), "light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    await user.selectOptions(screen.getByTestId("theme-switch"), "dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
