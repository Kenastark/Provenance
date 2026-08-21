import { expect, test } from "@playwright/test";
import { gotoRoute, setRole, setTheme, settleForSnapshot, waitForMapIdle } from "./support";

/**
 * Visual regression, both themes.
 *
 * The palette is fixed and every colour in the app resolves to a token, so an
 * unintended change to a token shows up here as a diff across several screens at
 * once - which is exactly the signal worth having. Update deliberately and read the
 * diff before accepting it.
 *
 * Baselines are per-platform, because font rasterisation and antialiasing differ
 * enough between macOS and Linux that one platform's baseline can never match the
 * other's run. Playwright names them accordingly and both sets are committed, so
 * the gate is real locally *and* in CI:
 *
 *     pnpm e2e:update           # this machine's baselines
 *     make web-visual-linux     # the Linux set, in the official Playwright image
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

  test(`alert centre — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/alerts");
    await setTheme(page, theme);
    await expect(page.getByRole("heading", { name: "Alert Centre" })).toBeVisible();
    // Scoped to the alert list, not the page: the Alert Centre and the
    // maintenance queue below it both render `data-table-row`, and each table
    // populates from its own independent fetch - an unscoped `.first()` can
    // race and grab a maintenance row on a run where that fetch settles first.
    const alertList = page.getByRole("region", { name: /^alert centre$/i });
    await alertList.getByTestId("data-table-row").first().click();
    await expect(page.getByTestId("alert-detail")).toBeVisible();
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot(`alert-centre-${theme}.png`, { fullPage: false });
  });

  test(`admin — ${theme}`, async ({ page }) => {
    await gotoRoute(page, "/");
    await setRole(page, "admin");
    await gotoRoute(page, "/admin");
    await setTheme(page, theme);
    await expect(page.getByTestId("rbac-matrix")).toBeVisible();
    await expect(page.getByTestId("infra-health-panel")).toBeVisible();
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot(`admin-${theme}.png`, { fullPage: false });
  });
}

test.describe("sign-in screen", () => {
  // Every other test in this file inherits the role `global-setup.ts` seeds into
  // storage, on purpose - that is what keeps their baselines showing the
  // dashboard unchanged. This screen only appears with nothing seeded, so it
  // opts back out to the browser's default (empty) storage.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("sign-in screen — dark", async ({ page }) => {
    // No account menu exists yet to reach the theme switch from, so dark - the
    // app's own default absent any preference - is exercised by doing nothing.
    await page.goto("/");
    await expect(page.getByTestId("signin-screen")).toBeVisible();
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot("signin-dark.png", { fullPage: false });
  });

  test("sign-in screen — light", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("provenance.theme", "light"));
    await page.goto("/");
    await expect(page.getByTestId("signin-screen")).toBeVisible();
    await settleForSnapshot(page);
    await expect(page).toHaveScreenshot("signin-light.png", { fullPage: false });
  });
});
