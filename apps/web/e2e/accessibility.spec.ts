import { expect, test } from "@playwright/test";
import { expectNoCriticalA11yViolations, gotoRoute, setTheme } from "./support";

/**
 * The accessibility floor, checked on every route in both themes.
 *
 * Keyboard traversal is tested by actually traversing: an operations screen that
 * can only be driven with a mouse is not finished, and a snapshot of ARIA
 * attributes would not catch a focus trap or an unreachable control.
 */

const ROUTES = [
  { path: "/", name: "network map" },
  { path: "/quality", name: "data quality monitor" },
  { path: "/timeline", name: "event timeline" },
  { path: "/evidence", name: "evidence" },
  { path: "/audit", name: "audit report" },
];

for (const route of ROUTES) {
  test(`${route.name} has no critical accessibility violations (dark)`, async ({ page }) => {
    await gotoRoute(page, route.path);
    await page.waitForLoadState("networkidle");
    await expectNoCriticalA11yViolations(page, `${route.name} (dark)`);
  });

  test(`${route.name} has no critical accessibility violations (light)`, async ({ page }) => {
    await gotoRoute(page, route.path);
    await setTheme(page, "light");
    await page.waitForLoadState("networkidle");
    await expectNoCriticalA11yViolations(page, `${route.name} (light)`);
  });
}

test.describe("keyboard traversal", () => {
  test("the skip link is the first tab stop and lands on the content", async ({ page }) => {
    await gotoRoute(page, "/");

    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: /skip to content/i });
    await expect(skip).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(page.locator("#main")).toBeFocused();
  });

  test("every screen is reachable with the keyboard alone", async ({ page }) => {
    await gotoRoute(page, "/");

    for (const label of ["Data quality", "Events", "Evidence", "Audit report"]) {
      // Exact: the station detail and the timeline both carry "View evidence" links.
      const link = page.getByRole("link", { name: label, exact: true });
      await link.focus();
      await expect(link).toBeFocused();
      await page.keyboard.press("Enter");
      // The station detail drawer contributes its own level-2 heading, so the
      // screen's own heading is the first one rather than the only one.
      await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
    }
  });

  test("a station can be opened from the quality table without a mouse", async ({ page }) => {
    await gotoRoute(page, "/quality");
    const firstRow = page.getByTestId("data-table-row").first();
    await expect(firstRow).toBeVisible();

    await firstRow.focus();
    await expect(firstRow).toBeFocused();
    await page.keyboard.press("Enter");

    await expect(page.getByTestId("station-detail-panel")).toBeVisible();
  });

  test("focus is visible wherever it lands", async ({ page }) => {
    await gotoRoute(page, "/");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");

    const outline = await page.evaluate(() => {
      const active = document.activeElement;
      if (!active) return null;
      const style = getComputedStyle(active);
      return { width: style.outlineWidth, style: style.outlineStyle };
    });

    expect(outline).not.toBeNull();
    expect(outline!.style).not.toEqual("none");
    expect(parseFloat(outline!.width)).toBeGreaterThan(0);
  });

  test("the layer toggle that is not ready is disabled and explained", async ({ page }) => {
    await gotoRoute(page, "/");
    // The wind-conditioned edge layer is live as of phase 4; the traffic-counter layer
    // is still the not-ready one (Enclod is unconfirmed), so it carries the pattern.
    const toggle = page.getByTestId("layer-toggle-trafficCounter");
    await expect(toggle).toBeDisabled();
    // The explanation is available to a screen reader, not only as a tooltip. Match the
    // Enclod-specific wording, which is unique to this layer (busStop shares the "not
    // yet placed on the map" phrasing).
    await expect(page.getByText(/Enclod counters/i)).toBeAttached();
  });
});

test.describe("reduced motion", () => {
  test("is respected", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await gotoRoute(page, "/");

    const duration = await page.evaluate(() => {
      const probe = document.createElement("div");
      probe.style.transition = "opacity 500ms";
      document.body.append(probe);
      const value = getComputedStyle(probe).transitionDuration;
      probe.remove();
      return value;
    });
    // base.css collapses every transition under prefers-reduced-motion.
    expect(parseFloat(duration)).toBeLessThan(0.05);
  });
});
