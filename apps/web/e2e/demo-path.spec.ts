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

    // SHAP, deweather, and attention are slots when a model artefact is absent,
    // never fabrications. `make demo-data` (this suite's fixture) deliberately never
    // trains any model - the pinned "everything degraded" state a fresh clone
    // actually shows (see Makefile's demo-data/demo-models split) - so both the
    // deweather and the (now real, backend-driven rather than hardcoded) attention
    // cards fall back to "not yet computed" here regardless of which defect is on
    // screen. SHAP's own degraded state uses a different data-testid and is not
    // counted by this locator.
    await expect(page.getByTestId("not-yet-computed")).toHaveCount(2);
    // The plume-vs-fault verdict is adjudicated per event on the timeline, not per
    // defect here; this panel points there rather than restating a verdict.
    await expect(page.getByTestId("evidence-verdict")).toContainText(
      "decided per event on the timeline",
    );
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

  test("events carry only real adjudicator verdicts, never a fabricated one", async ({ page }) => {
    await gotoRoute(page, "/timeline");
    const verdicts = page.getByTestId("event-verdict");

    // Snapshotting count() and then walking nth() races the list: the time window
    // resolves from the data and refilters the events, so an index can stop
    // resolving mid-loop. It is also vacuous if the count is zero at the moment it
    // is read. Wait for a settled, non-empty list, then read every label at once.
    await expect(verdicts.first()).toBeVisible();
    await expect(page.getByTestId("timeline-event").first()).toBeVisible();

    const labels = await verdicts.allTextContents();
    expect(labels.length, "the demo corpus must produce events to inspect").toBeGreaterThan(0);
    // Every label is one of the adjudicator's own verdicts (or the pending state) —
    // never an invented one. The wind-less demo corpus cannot corroborate a plume, so
    // its honest verdict is AMBIGUOUS ("Ambiguous — review"), routed to a human.
    const allowed = new Set([
      "pending adjudication",
      "Genuine plume",
      "Likely fault",
      "Ambiguous — review",
    ]);
    for (const label of labels) {
      expect(allowed.has(label.trim()), `unexpected verdict label: ${label}`).toBe(true);
    }
  });

  test("the quality monitor lists every station in the run", async ({ page }) => {
    const expectedStations = await apiStationCount(page);
    await gotoRoute(page, "/quality");
    await expect(page.getByTestId("data-table-row")).toHaveCount(expectedStations);
  });

  test("the Alert Centre ranks by risk, with severity and exposure legible beside it", async ({ page }) => {
    await gotoRoute(page, "/alerts");
    await expect(page.getByRole("heading", { name: "Alert Centre" })).toBeVisible();

    const list = page.getByRole("region", { name: /^alert centre$/i });
    for (const header of ["Severity", "Exposure", "Confidence", "Risk"]) {
      await expect(list.getByRole("columnheader", { name: new RegExp(header, "i") })).toBeVisible();
    }

    const rows = list.getByTestId("data-table-row");
    await expect(rows.first().or(page.getByText(/no candidate alerts/i))).toBeVisible();
    const count = await rows.count();
    test.skip(count === 0, "No candidate alerts in this run. Run `make demo-data`.");

    // Risk sorts descending by default - every consecutive pair must hold that order.
    const risks = await rows.evaluateAll((nodes) =>
      nodes.map((node) => Number(node.querySelector("strong")?.textContent ?? "NaN")),
    );
    for (let i = 1; i < risks.length; i += 1) {
      expect(risks[i - 1]).toBeGreaterThanOrEqual(risks[i]);
    }

    await rows.first().click();
    await expect(page.getByTestId("alert-detail")).toBeVisible();
    await expect(page.getByTestId("factor-breakdown")).toBeVisible();
  });
});

test.describe("no unrendered template reaches an operator", () => {
  // The reason-code sentences are templates filled from a detector's evidence. A
  // placeholder the UI could not fill must degrade to an em dash, never to a
  // literal "{parameter}" - which is precisely what the timeline shipped with,
  // because R07 keeps the parameter as a *column* rather than in its evidence dict.
  for (const path of ["/", "/quality", "/timeline", "/evidence", "/audit", "/alerts"]) {
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
