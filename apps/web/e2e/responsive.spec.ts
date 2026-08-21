import { expect, test } from "@playwright/test";
import { gotoRoute } from "./support";

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

test("the primary navigation stays reachable on a narrow screen", async ({ page }) => {
  await gotoRoute(page, "/");
  const nav = page.getByRole("navigation", { name: /primary/i });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "Audit report" })).toBeAttached();
  await expect(nav.getByRole("link", { name: "Alert Centre" })).toBeAttached();
});
