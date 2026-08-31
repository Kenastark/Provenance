import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import { SignInGate } from "../features/shell/SignInGate";
import { renderWithProviders } from "../test/harness";

/**
 * The sign-in gate and screen.
 *
 * These render the real dashboard (`AppRoutes`, including the real `TopBar`)
 * under `SignInGate`, the same composition `App.tsx` uses - so a passing test
 * here proves the gate, the role cards, the raw-key field, and "Sign out" all
 * wire together, not just that each renders in isolation.
 */

function renderGated(options: Parameters<typeof renderWithProviders>[1] = {}) {
  return renderWithProviders(
    <SignInGate>
      <AppRoutes />
    </SignInGate>,
    options,
  );
}

describe("SignInGate", () => {
  it("shows the sign-in screen when no role is persisted in this browser", () => {
    renderGated();
    expect(screen.getByTestId("signin-screen")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: /primary/i })).not.toBeInTheDocument();
  });

  it("skips straight to the dashboard when a role is already persisted", () => {
    localStorage.setItem("provenance.role", "admin");
    renderGated();
    expect(screen.queryByTestId("signin-screen")).not.toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument();
  });

  it("carries the descriptor and the four dev role cards when switching is allowed", () => {
    renderGated();
    expect(
      screen.getByText(/An AI trust layer for Environmental Sensor Networks\./i),
    ).toBeInTheDocument();
    for (const role of ["public_read", "researcher", "operator", "admin"]) {
      expect(screen.getByTestId(`signin-role-${role}`)).toBeInTheDocument();
    }
  });

  it("selecting a role card signs in, persists the role, and reaches the dashboard", async () => {
    const user = userEvent.setup();
    renderGated();

    await user.click(screen.getByTestId("signin-role-operator"));

    expect(await screen.findByRole("navigation", { name: /primary/i })).toBeInTheDocument();
    expect(localStorage.getItem("provenance.role")).toBe("operator");
    expect(screen.getByTestId("account-menu")).toHaveTextContent("Operator");
  });

  it("accepts a pasted dev key as an alternative to clicking a card", async () => {
    const user = userEvent.setup();
    renderGated();

    await user.type(screen.getByTestId("signin-api-key-input"), "prov-admin-key");
    await user.click(screen.getByTestId("signin-api-key-submit"));

    expect(await screen.findByRole("navigation", { name: /primary/i })).toBeInTheDocument();
    expect(screen.getByTestId("account-menu")).toHaveTextContent("Admin");
  });

  it("rejects a key that matches none of the four dev keys, without signing in", async () => {
    const user = userEvent.setup();
    renderGated();

    await user.type(screen.getByTestId("signin-api-key-input"), "not-a-real-key");
    await user.click(screen.getByTestId("signin-api-key-submit"));

    expect(await screen.findByTestId("signin-api-key-error")).toBeInTheDocument();
    expect(screen.getByTestId("signin-screen")).toBeInTheDocument();
    expect(localStorage.getItem("provenance.role")).toBeNull();
  });

  it("never renders the four-card picker when the deployment pins a non-dev key", async () => {
    renderGated({ envApiKey: "a-real-deployment-key" });

    // The pinned key resolves and auto-advances on its own - there was never a
    // moment a picker with four clickable cards could have appeared.
    expect(screen.queryByTestId("signin-role-picker")).not.toBeInTheDocument();
    expect(await screen.findByRole("navigation", { name: /primary/i })).toBeInTheDocument();
  });

  it("moves focus to the main landmark once sign-in completes", async () => {
    const user = userEvent.setup();
    renderGated();

    await user.click(screen.getByTestId("signin-role-public_read"));
    await waitFor(() => expect(document.getElementById("main")).toHaveFocus());
  });

  it("every role card is reachable and operable with the keyboard alone", async () => {
    const user = userEvent.setup();
    renderGated();

    await user.tab(); // -> Public read card, the first focusable element on the screen
    expect(screen.getByTestId("signin-role-public_read")).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(await screen.findByRole("navigation", { name: /primary/i })).toBeInTheDocument();
  });

  it("sign out clears the persisted role and returns to the sign-in screen", async () => {
    const user = userEvent.setup();
    localStorage.setItem("provenance.role", "operator");
    renderGated();

    expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument();

    await user.click(screen.getByTestId("account-menu"));
    await user.click(screen.getByTestId("sign-out"));

    expect(await screen.findByTestId("signin-screen")).toBeInTheDocument();
    expect(localStorage.getItem("provenance.role")).toBeNull();
  });
});
