import { expect, test } from "@playwright/test";
import { apiStationCount, gotoRoute, setTheme } from "./support";

/**
 * The demo path, end to end, in a real browser against a real API.
 *
 * This is the run-through that happens on stage: the map, the deceptive
 * completeness figure beside the defect count, a drill-down to an individual
 * wrong-but-plausible reading, and the evidence behind it.
 */

test.describe("the demo path", () => {
  test("map → station → reason code → evidence", async ({ page }) => {
    const expectedMarkers = await apiStationCount(page);
    expect(
      expectedMarkers,
      "The demo corpus must be loaded. Run: make demo-data",
    ).toBeGreaterThan(0);

    // ------------------------------------------------------------ the map
    await gotoRoute(page, "/");
    const markers = page.getByTestId("station-marker");
    await expect(markers).toHaveCount(expectedMarkers);

    // Every marker carries a shape as well as a colour.
    const shapes = await page.locator("[data-testid='station-marker'] svg").evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-shape")),
    );
    expect(shapes.every(Boolean)).toBe(true);

    // ------------------------------------------------- the station detail
    await markers.first().click();
    const panel = page.getByTestId("station-detail-panel");
    await expect(panel).toBeVisible();

    // A trust score never renders without its breakdown and a reason code.
    await expect(panel.getByTestId("trust-chip")).toBeVisible();
    await expect(panel.getByTestId("trust-breakdown")).toBeVisible();

    const reasons = panel.getByTestId("station-reason-codes");
    await expect(reasons.getByTestId("reason-code-badge").first()).toBeVisible();

    // The reason must be a sentence, not a bare code, and must not leak a raw
    // placeholder onto an operator's screen.
    const sentence = await reasons.getByTestId("reason-code-badge").first().innerText();
    expect(sentence).toMatch(/[a-z]{3,}\s+[a-z]{3,}/i);
    expect(sentence).not.toMatch(/\{[a-z_]+\}/i);

    // ------------------------------------------------------ the evidence
    await panel.getByRole("link", { name: "View evidence" }).click();
    await expect(page).toHaveURL(/\/evidence\?station=/);
    await expect(page.getByRole("heading", { name: "Evidence", exact: true })).toBeVisible();
  });

  test("the defect table renders with its evidence", async ({ page }) => {
    await gotoRoute(page, "/evidence");
    await expect(page.getByTestId("defect-table")).toBeVisible();
    await expect(page.getByTestId("data-table-row").first()).toBeVisible();

    const evidence = page.getByTestId("defect-evidence");
    await expect(evidence).toBeVisible();
    await expect(evidence.getByTestId("reason-code-badge").first()).toBeVisible();

    // SHAP and attention are slots, not fabrications.
    await expect(page.getByTestId("not-yet-computed")).toHaveCount(2);
    await expect(page.getByTestId("evidence-verdict")).toContainText("pending adjudication");
  });

  test("the audit report shows the completeness figure beside the defect rate", async ({ page }) => {
    await gotoRoute(page, "/audit");

    const headline = page.getByTestId("audit-headline");
    await expect(headline).toBeVisible();
    await expect(headline).toContainText("Conventional completeness");
    await expect(headline).toContainText("Defect rate");

    // The definition sits with the number, not in a footnote.
    const definition = page.getByTestId("defect-rate-definition");
    await expect(definition).toContainText("Defective cells ÷ covered cells");
    await expect(definition).toContainText("Structural absences");

    // Both figures are computed, so they must actually be numbers on screen.
    await expect(headline).toContainText(/\d+\.\d+%/);
  });

  test("events are listed and none claims a verdict", async ({ page }) => {
    await gotoRoute(page, "/timeline");
    const verdicts = page.getByTestId("event-verdict");
    const count = await verdicts.count();
    for (let index = 0; index < count; index += 1) {
      await expect(verdicts.nth(index)).toHaveText("pending adjudication");
    }
  });

  test("the quality monitor lists every station in the run", async ({ page }) => {
    const expectedStations = await apiStationCount(page);
    await gotoRoute(page, "/quality");
    await expect(page.getByTestId("data-table-row")).toHaveCount(expectedStations);
  });
});

test.describe("no unrendered template reaches an operator", () => {
  // The reason-code sentences are templates filled from a detector's evidence. A
  // placeholder the UI could not fill must degrade to an em dash, never to a
  // literal "{parameter}" - which is precisely what the timeline shipped with,
  // because R07 keeps the parameter as a *column* rather than in its evidence dict.
  for (const path of ["/", "/quality", "/timeline", "/evidence", "/audit"]) {
    test(`${path} renders no raw placeholder`, async ({ page }) => {
      await gotoRoute(page, path);
      await page.waitForLoadState("networkidle");
      const text = await page.locator("body").innerText();
      const offenders = text.match(/\{[a-z_]+\}/gi) ?? [];
      expect(offenders, `Unfilled placeholders on ${path}`).toEqual([]);
    });
  }
});

test.describe("theme", () => {
  test("switches between a fully implemented dark and light", async ({ page }) => {
    await gotoRoute(page, "/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    const background = () =>
      page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const dark = await background();

    await setTheme(page, "light");
    const light = await background();
    expect(light).not.toEqual(dark);

    // The map re-themes with everything else rather than staying dark.
    const mapGround = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--prov-map-ground").trim(),
    );
    expect(mapGround).not.toEqual("");

    await setTheme(page, "dark");
    expect(await background()).toEqual(dark);
  });

  test("remembers the choice across a reload", async ({ page }) => {
    await gotoRoute(page, "/");
    await setTheme(page, "light");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});
