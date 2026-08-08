import { expect, test } from "@playwright/test";
import { gotoRoute, setTheme, settleForSnapshot, waitForMapIdle } from "./support";

/**
 * Visual regression, both themes.
 *
 * The palette is fixed and every colour in the app resolves to a token, so an
 * unintended change to a token shows up here as a diff across several screens at
 * once - which is exactly the signal worth having. Update deliberately with
 * `pnpm e2e:update` and read the diff before accepting it.
 */

const THEMES = ["dark", "light"] as const;

for (const theme of THEMES) {
  test(`network map — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/");
    await setTheme(page, theme);
    await expect(page.getByTestId("station-marker").first()).toBeVisible();
    await waitForMapIdle(page);
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot(`map-${theme}.png`, { fullPage: false });
  });

  test(`station detail — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/");
    await setTheme(page, theme);
    await waitForMapIdle(page);
    await page.getByTestId("station-marker").first().click();
    const panel = page.getByTestId("station-detail-panel");
    await expect(panel.getByTestId("trust-breakdown")).toBeVisible();
    await settleForSnapshot(page);
    await expect(panel).toHaveScreenshot(`station-detail-${theme}.png`);
  });

  test(`data quality monitor — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/quality");
    await setTheme(page, theme);
    await expect(page.getByTestId("data-table-row").first()).toBeVisible();
    await settleForSnapshot(page);
    await expect(page.getByTestId("data-table")).toHaveScreenshot(`quality-monitor-${theme}.png`);
  });

  test(`event timeline — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/timeline");
    await setTheme(page, theme);
    await expect(page.getByRole("heading", { name: "Events" })).toBeVisible();
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot(`timeline-${theme}.png`, { fullPage: false });
  });
}
