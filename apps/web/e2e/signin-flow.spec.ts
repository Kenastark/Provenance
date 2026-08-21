import { expect, test } from "@playwright/test";
import { waitForMapIdle } from "./support";

/**
 * The sign-in gate, end to end, in a real browser with real storage.
 *
 * `global-setup.ts` seeds a role for every other spec in the suite; this one
 * deliberately starts from nothing, the same as a browser that has never opened
 * this app before.
 */

test.describe("sign-in flow", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("choosing a role lands on the network map, survives a reload, and sign out returns to sign-in", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByTestId("signin-screen")).toBeVisible();
    await expect(page.getByRole("navigation", { name: /primary/i })).not.toBeVisible();

    await page.getByTestId("signin-role-operator").click();

    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
    await waitForMapIdle(page);
    await expect(page.getByTestId("station-marker").first()).toBeVisible();

    // The choice persisted, so a reload does not send the operator back to the
    // sign-in screen.
    await page.reload();
    await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
    await expect(page.getByTestId("signin-screen")).not.toBeVisible();

    await page.getByTestId("account-menu").click();
    await page.getByTestId("sign-out").click();

    await expect(page.getByTestId("signin-screen")).toBeVisible();
    await expect(page.getByRole("navigation", { name: /primary/i })).not.toBeVisible();
  });
});
