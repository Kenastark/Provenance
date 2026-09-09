import { expect, test } from "@playwright/test";
import { gotoRoute, openChromeIfCollapsed, waitForMapIdle } from "./support";

/**
 * The 390px floor.
 *
 * An operator on a phone at a roadside cabinet is a real user of this screen. The
 * check that matters is that the page never scrolls horizontally: wide content
 * (the dense tables, the timeline axis) has to scroll inside its own container
 * instead of pushing the whole document sideways.
 */

const ROUTES = ["/", "/quality", "/timeline", "/evidence", "/audit", "/alerts", "/admin"];

for (const path of ROUTES) {
  test(`${path} does not scroll the page horizontally at 390px`, async ({ page }) => {
    await gotoRoute(page, path);
    await page.waitForLoadState("networkidle");

    const overflow = await page.evaluate(() => {
      // Two questions, because either alone can pass while the layout is broken.
      // First: does the document scroll sideways? Second, and stricter: is there
      // any element sticking out past the viewport whose ancestors do NOT clip it?
      // Wide content is allowed - it just has to scroll inside its own container.
      const escaping: string[] = [];
      const walk = (element: Element) => {
        for (const child of Array.from(element.children)) {
          const node = child as HTMLElement;
          const style = getComputedStyle(node);
          const box = node.getBoundingClientRect();
          if (box.right > window.innerWidth + 1 && box.width > 0) {
            escaping.push(`${node.tagName}.${String(node.className).slice(0, 40)}`);
          }
          const clips = ["auto", "hidden", "scroll"].includes(style.overflowX);
          if (!clips) walk(child);
        }
      };
      walk(document.body);
      return {
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        escaping: escaping.slice(0, 5),
      };
    });

    expect(overflow.escaping, "Elements escaping the viewport unclipped").toEqual([]);
    // A pixel of slack for sub-pixel rounding in the layout engine.
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
  });
}

test("the dense table scrolls inside its own container", async ({ page }) => {
  await gotoRoute(page, "/quality");
  const scroller = page.getByTestId("data-table-scroll");
  await expect(scroller).toBeVisible();

  const scrollable = await scroller.evaluate((node) => ({
    canScroll: node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight,
    overflow: getComputedStyle(node).overflow,
  }));
  expect(scrollable.overflow).toContain("auto");
});

/**
 * The checks below describe the *collapsed* layout specifically, so they only mean
 * anything on a viewport that collapses it. This file is run by both projects -
 * the `mobile` project at 390px and `chromium` at 1440px, where the overflow loop
 * above is still a useful (weaker) assertion - so these three opt out by width
 * rather than being moved to a file the desktop project ignores.
 */
const COLLAPSE_BREAKPOINT = 1280;

test("the primary navigation stays reachable on a narrow screen", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? COLLAPSE_BREAKPOINT) >= COLLAPSE_BREAKPOINT, "chrome not collapsed");
  await gotoRoute(page, "/");

  // Collapsed, not dropped. The bar cannot hold seven links plus the window,
  // theme and account controls at this width, so they sit behind one button -
  // but every one of them still has to be reachable, which is what this asserts.
  const toggle = page.getByTestId("topbar-menu-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");

  const nav = page.getByRole("navigation", { name: /primary/i });
  await expect(nav).toBeHidden();

  await openChromeIfCollapsed(page);
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(nav).toBeVisible();

  // Every screen this role can reach, not a sample of two: a menu that quietly
  // drops a destination is the failure this test exists to catch.
  for (const label of ["Network map", "Data quality", "Events", "Evidence", "Audit report"]) {
    await expect(nav.getByRole("link", { name: label })).toBeVisible();
  }

  // The controls that were beside the nav on a desktop bar came with it.
  await expect(page.getByTestId("theme-switch")).toBeVisible();
  await expect(page.getByTestId("account-menu")).toBeVisible();

  // And it closes again, so the map is not left behind a panel.
  await page.keyboard.press("Escape");
  await expect(nav).toBeHidden();
});

test("every control in the collapsed menu is a real touch target", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? COLLAPSE_BREAKPOINT) >= COLLAPSE_BREAKPOINT, "chrome not collapsed");
  await gotoRoute(page, "/");
  await openChromeIfCollapsed(page);

  // 44px is the documented iOS/Android minimum. The tokens carry it below `lg`,
  // so this is really asserting that the compact token block reached these
  // controls rather than that each one hardcoded a height.
  const nav = page.getByRole("navigation", { name: /primary/i });
  for (const label of ["Network map", "Audit report"]) {
    const box = await nav.getByRole("link", { name: label }).boundingBox();
    expect(box, `${label} must be laid out`).not.toBeNull();
    expect(box!.height, `${label} tap target`).toBeGreaterThanOrEqual(44);
  }

  const toggleBox = await page.getByTestId("topbar-menu-toggle").boundingBox();
  expect(toggleBox!.height, "menu button tap target").toBeGreaterThanOrEqual(44);
});

test("the station detail overlays the map rather than stacking under it", async ({ page, viewport }) => {
  // The sheet is a below-`lg` layout; from `lg` up it is the side rail that
  // drawer-resize.spec.ts covers instead.
  test.skip((viewport?.width ?? 1024) >= 1024, "the detail is a side rail from lg up");
  await gotoRoute(page, "/");

  const mapSection = page.getByRole("region", { name: "Network map" });
  const mapBefore = await mapSection.boundingBox();

  await page.getByTestId("station-marker").first().click();
  const sheet = page.getByTestId("station-detail-panel");
  await expect(sheet).toBeVisible();
  await waitForMapIdle(page);

  const mapAfter = await mapSection.boundingBox();
  const sheetBox = await sheet.boundingBox();

  // The map keeps its height: the sheet is drawn over it, not wedged beside it.
  // Stacked in the same flex column - the layout this replaced - opening a
  // station roughly halved the map instead.
  expect(mapAfter!.height).toBeCloseTo(mapBefore!.height, 0);

  // And it really is on top: the sheet's top edge sits inside the map's box.
  expect(sheetBox!.y).toBeGreaterThan(mapAfter!.y);
  expect(sheetBox!.y).toBeLessThan(mapAfter!.y + mapAfter!.height);

  // Enough map is left to see where the selected station actually is.
  expect(sheetBox!.height).toBeLessThanOrEqual(mapAfter!.height * 0.75);
});

test("the sign-in screen never scrolls the page sideways", async ({ page }) => {
  // Deliberately unguarded, so it runs at both project widths: the point is that
  // the route loop above cannot reach this screen at all. Every other spec starts
  // from a pre-seeded role, so the one screen a first-time visitor sees had never
  // been measured at 390px - and it carried a fixed 1120px hero row and a nowrap
  // headline that were simply clipped by #root's overflow.
  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();

  await expect(page.getByTestId("signin-screen")).toBeVisible();
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
});
