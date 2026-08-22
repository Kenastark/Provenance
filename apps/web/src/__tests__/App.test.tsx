import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("shows the Alert Centre tab for the default operator role, but not Admin", async () => {
    renderWithProviders(<AppRoutes />);
    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(within(nav).getByRole("link", { name: "Alert Centre" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });

  it("reveals the Admin tab once the role is switched", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />);

    await user.click(screen.getByTestId("account-menu"));
    expect(screen.getByTestId("account-menu")).toHaveTextContent("Operator");

    // The Alert Centre is reachable directly, since operator grants it.
    await user.click(screen.getByRole("link", { name: "Alert Centre" }));
    expect(await screen.findByRole("heading", { name: "Alert Centre" })).toBeInTheDocument();

    await user.selectOptions(screen.getByTestId("role-switch"), "admin");
    expect(screen.getByTestId("account-menu")).toHaveTextContent("Admin");

    const nav = screen.getByRole("navigation", { name: /primary/i });
    await user.click(within(nav).getByRole("link", { name: "Admin" }));
    expect(await screen.findByRole("heading", { name: "Admin", level: 2 })).toBeInTheDocument();
  });

  it("blocks the /admin route in words an operator could read aloud, for a role that does not reach it", async () => {
    renderWithProviders(<AppRoutes />, { route: "/admin" });
    const blocked = await screen.findByTestId("role-forbidden");
    expect(blocked).toHaveTextContent(/signed in as operator/i);
    expect(blocked).toHaveTextContent(/requires admin or above/i);
  });

  it("defaults the time window to a bounded one, not the full corpus", () => {
    renderWithProviders(<AppRoutes />);
    expect(screen.getByLabelText(/window/i)).toHaveValue("7d");
  });

  it("shows the whole network's data freshness against real time, not the per-station anchor", async () => {
    renderWithProviders(<AppRoutes />);
    const freshness = await screen.findByTestId("data-freshness");
    // The fixture's anchor (newest reading network-wide) is fixed; this text must
    // stay measured against the real clock (unlike the station drawer's own "last
    // reading", which is deliberately anchor-relative) so it keeps reading as
    // increasingly old for a corpus that never advances, rather than always
    // looking current relative only to itself.
    expect(freshness).toHaveTextContent("14 May 2026, 23:00 UTC");
    expect(freshness).toHaveTextContent(/ago/i);
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
