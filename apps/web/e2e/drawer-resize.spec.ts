import { expect, test } from "@playwright/test";
import { gotoRoute, waitForMapIdle } from "./support";

/**
 * The station detail drawer's resize handle.
 *
 * Playwright gives every test a fresh, empty browser context by default (no
 * `storageState` is configured anywhere in this suite), so the width one test
 * drags to never leaks into another test's storage - which matters here more than
 * usual, because a leaked width would silently shift every visual baseline in
 * visual.spec.ts to whatever was last dragged.
 */

const STORAGE_KEY = "provenance.drawer-width";

async function openStationDetail(page: import("@playwright/test").Page) {
  await gotoRoute(page, "/");
  await waitForMapIdle(page);
  await page.getByTestId("station-marker").first().click();
  const panel = page.getByTestId("station-detail-panel");
  await expect(panel.getByTestId("trust-breakdown")).toBeVisible();
  return panel;
}

async function dragHandleBy(
  page: import("@playwright/test").Page,
  handle: ReturnType<import("@playwright/test").Page["getByTestId"]>,
  deltaX: number,
) {
  const box = await handle.boundingBox();
  if (!box) throw new Error("resize handle has no layout box");
  const startX = box.x + box.width / 2;
  const startY = box.y + box.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + deltaX, startY, { steps: 10 });
  await page.mouse.up();
}

test("dragging the handle widens the panel and shrinks the map by the same amount, and the width survives a reload", async ({
  page,
}) => {
  const panel = await openStationDetail(page);
  const map = page.locator('[aria-label="Network map"]');
  const handle = page.getByTestId("drawer-resize-handle");

  const panelBefore = await panel.boundingBox();
  const mapBefore = await map.boundingBox();
  if (!panelBefore || !mapBefore) throw new Error("missing layout box");

  // The handle sits on the panel's left edge: dragging it left widens the panel.
  await dragHandleBy(page, handle, -120);

  const panelAfter = await panel.boundingBox();
  const mapAfter = await map.boundingBox();
  if (!panelAfter || !mapAfter) throw new Error("missing layout box");

  expect(panelAfter.width).toBeGreaterThan(panelBefore.width + 80);
  expect(mapAfter.width).toBeLessThan(mapBefore.width - 80);
  // The map and the panel share one flex row - what the panel gains, the map
  // gives up, give or take the handle's own few px.
  const combinedBefore = panelBefore.width + mapBefore.width;
  const combinedAfter = panelAfter.width + mapAfter.width;
  expect(Math.abs(combinedAfter - combinedBefore)).toBeLessThan(10);

  const stored = await page.evaluate((key) => localStorage.getItem(key), STORAGE_KEY);
  expect(Number(stored)).toBeCloseTo(panelAfter.width, -1);

  await page.reload();
  await waitForMapIdle(page);
  const panelAfterReload = page.getByTestId("station-detail-panel");
  await expect(panelAfterReload.getByTestId("trust-breakdown")).toBeVisible();
  const restoredBox = await panelAfterReload.boundingBox();
  expect(restoredBox).not.toBeNull();
  expect(Math.abs(restoredBox!.width - panelAfter.width)).toBeLessThan(5);
});

test("double-clicking the handle resets the panel to the token default width", async ({ page }) => {
  const panel = await openStationDetail(page);
  const handle = page.getByTestId("drawer-resize-handle");

  await dragHandleBy(page, handle, -100);
  const widened = await panel.boundingBox();
  if (!widened) throw new Error("missing layout box");

  await handle.dblclick();

  const defaultWidth = await page.evaluate(() =>
    Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--prov-drawer-width")),
  );
  const reset = await panel.boundingBox();
  if (!reset) throw new Error("missing layout box");

  expect(reset.width).toBeLessThan(widened.width);
  expect(Math.abs(reset.width - defaultWidth)).toBeLessThan(5);
  expect(await page.evaluate((key) => localStorage.getItem(key), STORAGE_KEY)).toBeNull();
});

test("the handle is a keyboard-operable separator: arrow keys resize, and it carries an accessible name", async ({
  page,
}) => {
  const panel = await openStationDetail(page);
  const handle = page.getByTestId("drawer-resize-handle");

  await expect(handle).toHaveAttribute("role", "separator");
  await expect(handle).toHaveAttribute("aria-orientation", "vertical");
  await expect(handle).toHaveAccessibleName(/resize/i);

  await handle.focus();
  await expect(handle).toBeFocused();

  const before = await panel.boundingBox();
  if (!before) throw new Error("missing layout box");

  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  const widened = await panel.boundingBox();
  if (!widened) throw new Error("missing layout box");
  expect(widened.width).toBeGreaterThan(before.width);

  await page.keyboard.press("ArrowRight");
  const narrowed = await panel.boundingBox();
  if (!narrowed) throw new Error("missing layout box");
  expect(narrowed.width).toBeLessThan(widened.width);
});
