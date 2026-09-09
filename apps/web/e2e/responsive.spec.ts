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

test("every tab in the collapsed menu actually navigates", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? COLLAPSE_BREAKPOINT) >= COLLAPSE_BREAKPOINT, "chrome not collapsed");
  await gotoRoute(page, "/");

  // Regression test with a story. The first version of the collapsed menu put the
  // tap-outside-to-dismiss backdrop inside the header, at `z-drawer`, while the
  // panel itself was left at `z-auto`. Both share the header's stacking context,
  // so the backdrop painted *over* the open menu: every link was present, visible,
  // and correctly labelled, and every tap on one landed on the backdrop instead -
  // the menu closed and nothing navigated.
  //
  // The point of this test is that `toBeVisible()` cannot catch that. Visibility
  // is not hit-testability. So this clicks each tab for real and checks the URL
  // moved, and asserts the element at the link's own centre point is the link.
  const nav = page.getByRole("navigation", { name: /primary/i });
  const tabs: [string, string][] = [
    ["Data quality", "/quality"],
    ["Events", "/timeline"],
    ["Evidence", "/evidence"],
    ["Audit report", "/audit"],
    ["Network map", "/"],
  ];

  for (const [label, path] of tabs) {
    await openChromeIfCollapsed(page);
    const link = nav.getByRole("link", { name: label });
    await expect(link).toBeVisible();

    const box = await link.boundingBox();
    expect(box, `${label} must be laid out`).not.toBeNull();
    const topmost = await page.evaluate(
      ({ x, y }) => {
        const element = document.elementFromPoint(x, y);
        return element?.closest("a") ? "link" : (element?.getAttribute("data-testid") ?? "other");
      },
      { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2 },
    );
    expect(topmost, `nothing may cover the "${label}" tab`).toBe("link");

    await link.click();
    // A plain string predicate, not a hand-built regex: escaping only "/" (as an
    // earlier version of this line did) leaves every other regex metacharacter
    // live, which is exactly the class of bug CodeQL's incomplete-escaping check
    // exists to catch - these paths are literals today, but the pattern itself
    // was still wrong.
    await expect(page).toHaveURL((url) => url.pathname === path);
    // Following a link closes the menu, so the screen it just opened is visible.
    await expect(nav).toBeHidden();
  }
});

test("the account controls in the collapsed menu are hit-testable", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? COLLAPSE_BREAKPOINT) >= COLLAPSE_BREAKPOINT, "chrome not collapsed");
  await gotoRoute(page, "/");
  await openChromeIfCollapsed(page);

  // Second instance of the same bug class as the tab-tap regression above, so it
  // gets the same kind of assertion. The account panel was absolutely positioned,
  // which inside the collapsed menu put it outside the panel's scroll box - Sign
  // out laid out past the panel's bottom edge, in territory the dismiss backdrop
  // owns. Playwright's own click still passed, because `click()` scrolls the
  // element into view first; only a hit test at the element's resting position
  // shows it. `toBeVisible()` never would have.
  await page.getByTestId("account-menu").click();

  for (const testId of ["role-switch", "sign-out"]) {
    const control = page.getByTestId(testId);
    await expect(control).toBeVisible();
    const box = await control.boundingBox();
    expect(box, `${testId} must be laid out`).not.toBeNull();
    const topmost = await page.evaluate(
      ({ x, y, id }) => {
        const element = document.elementFromPoint(x, y);
        return element?.closest(`[data-testid="${id}"]`) ? id : (element?.getAttribute("data-testid") ?? "other");
      },
      { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2, id: testId },
    );
    expect(topmost, `nothing may cover ${testId}`).toBe(testId);
  }

  await page.getByTestId("sign-out").click();
  await expect(page.getByTestId("signin-screen")).toBeVisible();
});

test("tapping outside the collapsed menu dismisses it", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? COLLAPSE_BREAKPOINT) >= COLLAPSE_BREAKPOINT, "chrome not collapsed");
  await gotoRoute(page, "/");

  const nav = page.getByRole("navigation", { name: /primary/i });
  await openChromeIfCollapsed(page);
  await expect(nav).toBeVisible();

  // Low on the screen, clear of the panel. The backdrop still has to receive this
  // - raising the panel above it must not disable dismissal.
  const size = page.viewportSize()!;
  await page.mouse.click(size.width / 2, size.height - 40);
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
