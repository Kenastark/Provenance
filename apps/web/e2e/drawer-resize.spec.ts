import { expect, test } from "@playwright/test";
import { easternmostStationId, gotoRoute, waitForMapIdle } from "./support";

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

test("resizing the drawer keeps the GL canvas in sync with its container, so the network's easternmost station stays over painted tiles", async ({
  page,
}) => {
  // Regression test (real-drop symptom: DEB-KER12 floating in a blank grey box).
  // MapLibre's own internal resize observer is debounced and raced React's
  // layout commit, leaving the canvas at a stale pixel size while the marker
  // overlay (plain CSS, zero lag) already reflected the container's new box.
  // Whichever station sits at the extreme east of the loaded corpus lands at the
  // fitted view's right edge - the one marker a canvas/container size mismatch
  // pushes past the last painted pixel. Derived from the API, not hardcoded to
  // the real station id, so this holds against the synthetic corpus CI loads.
  const eastId = await easternmostStationId(page);
  await openStationDetail(page);
  const mapSection = page.locator('[aria-label="Network map"]');
  const canvas = page.locator('[data-testid="map-canvas"] canvas');
  const handle = page.getByTestId("drawer-resize-handle");

  await dragHandleBy(page, handle, -150);
  await waitForMapIdle(page);

  const containerBox = await mapSection.boundingBox();
  const canvasBox = await canvas.boundingBox();
  if (!containerBox || !canvasBox) throw new Error("missing layout box");

  // The canvas's own rendered box must track its container's, not lag behind it.
  expect(Math.abs(canvasBox.width - containerBox.width)).toBeLessThan(2);
  expect(Math.abs(canvasBox.height - containerBox.height)).toBeLessThan(2);

  const eastMarker = page.locator(`[data-testid="station-marker"][data-station="${eastId}"]`);
  await expect(eastMarker).toBeVisible();
  const markerBox = await eastMarker.boundingBox();
  if (!markerBox) throw new Error(`${eastId} marker has no layout box`);

  // The marker must sit within the canvas's actually-painted area, not past its
  // right edge in the container's bare background.
  expect(markerBox.x).toBeGreaterThanOrEqual(canvasBox.x);
  expect(markerBox.x + markerBox.width).toBeLessThanOrEqual(canvasBox.x + canvasBox.width + 1);
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
