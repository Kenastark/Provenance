import { expect, test, type Page } from "@playwright/test";
import { gotoRoute } from "./support";

/** The Alert Centre and the maintenance queue below it both render
 * `data-table-row`, each from its own independent fetch - scoping to the alert
 * list avoids a race where the maintenance fetch settles first and an unscoped
 * `.first()` grabs one of its rows instead. */
function alertRows(page: Page) {
  return page.getByRole("region", { name: /^alert centre$/i }).getByTestId("data-table-row");
}

/**
 * The frontend half of standing rule 5, walked end to end against the real API.
 *
 * The backend half is `test_signoff_gate.py`'s static call-graph proof that
 * `gate.dispatch` cannot deliver without calling `validate_signoff` first, and that
 * nothing else in the codebase can reach a channel sender. This spec proves the
 * *other* direction: that the only UI path to a dispatch also cannot be reached
 * without recording a sign-off first - the dispatch button stays disabled, with the
 * reason stated on screen, until one exists. Dispatch itself is offline by
 * construction (`channels.py`) - this never performs real network egress.
 */

test.describe("sign-off and dispatch gate", () => {
  test("dispatch is blocked until a sign-off is recorded, then completes", async ({ page }) => {
    await gotoRoute(page, "/alerts");
    await expect(page.getByRole("heading", { name: "Alert Centre" })).toBeVisible();

    const firstRow = alertRows(page).first();
    await expect(firstRow, "The Alert Centre needs at least one candidate alert. Run `make demo-data`.").toBeVisible();
    await firstRow.click();

    const dispatchButton = page.getByTestId("dispatch-button");
    await expect(dispatchButton).toBeVisible();
    await expect(dispatchButton).toBeDisabled();
    await expect(page.getByTestId("dispatch-blocked")).toContainText(/no valid, unexpired sign-off/i);

    await page.getByTestId("signoff-operator").fill("e2e-operator");
    await page.getByRole("button", { name: /record sign-off/i }).click();

    await expect(page.getByTestId("signoff-records")).toContainText(/valid/i);
    await expect(page.getByTestId("signoff-records")).toContainText(/e2e-operator/i);
    await expect(dispatchButton).toBeEnabled();

    await dispatchButton.click();
    await expect(page.getByTestId("dispatch-success")).toBeVisible();
    await expect(page.getByTestId("dispatch-success")).toContainText(/status sent/i);
  });

  test("the dispatch button is structurally unreachable before a sign-off exists", async ({ page }) => {
    await gotoRoute(page, "/alerts");
    await alertRows(page).first().click();

    const dispatchButton = page.getByTestId("dispatch-button");
    await expect(dispatchButton).toBeVisible();
    // `disabled` removes an element from the tab order in every engine this suite
    // targets - proving the property, not just that a click has no effect, is what
    // makes this the same guarantee a screen reader user gets.
    await expect(dispatchButton).toHaveJSProperty("disabled", true);
  });

  test("switching to a different alert resets the sign-off form to that alert", async ({ page }) => {
    await gotoRoute(page, "/alerts");
    const rows = alertRows(page);
    await expect(rows.first()).toBeVisible();
    const count = await rows.count();
    test.skip(count < 2, "Needs at least two candidate alerts to prove the form resets per alert.");

    await rows.first().click();
    await page.getByTestId("signoff-operator").fill("first-alert-operator");

    await rows.nth(1).click();
    await expect(page.getByTestId("signoff-operator")).not.toHaveValue("first-alert-operator");
    await expect(page.getByTestId("dispatch-button")).toBeDisabled();
  });
});
