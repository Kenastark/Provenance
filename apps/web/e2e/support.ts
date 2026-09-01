import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/**
 * Shared helpers for the end-to-end suite.
 *
 * The counts these helpers assert against come from the API, never from a literal
 * in a test. "18 markers" is only meaningful if 18 is what the network actually
 * has; hardcoding it would make the test pass on a corpus it no longer describes,
 * which is the same failure mode Provenance exists to catch.
 */

export const API_BASE_URL = process.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const API_KEY = process.env.VITE_API_KEY ?? "prov-operator-key";

export async function apiStationCount(page: Page): Promise<number> {
  const response = await page.request.get(`${API_BASE_URL}/v1/stations?limit=500`, {
    headers: { "X-API-Key": API_KEY },
  });
  expect(response.ok(), `The API must be serving data. Run: make demo-data`).toBeTruthy();
  const body = (await response.json()) as { items: { lat: number | null }[] };
  return body.items.filter((station) => station.lat !== null).length;
}

/**
 * The station id sitting at the extreme east of the network - whichever corpus is
 * loaded, real or synthetic. `boundsForStations` fits the map to every located
 * station, so this one always lands at the fitted view's right edge, which is
 * exactly the edge a resizable panel shrinks the map into. Deriving it from the
 * API rather than naming a real station (`DEB-KER12`) keeps the test meaningful
 * against the synthetic corpus this suite actually loads in CI.
 */
export async function easternmostStationId(page: Page): Promise<string> {
  const response = await page.request.get(`${API_BASE_URL}/v1/stations?limit=500`, {
    headers: { "X-API-Key": API_KEY },
  });
  expect(response.ok(), `The API must be serving data. Run: make demo-data`).toBeTruthy();
  const body = (await response.json()) as {
    items: { station_id: string; lat: number | null; lon: number | null }[];
  };
  const located = body.items.filter(
    (s): s is { station_id: string; lat: number; lon: number } => s.lat !== null && s.lon !== null,
  );
  expect(located.length, "at least one located station is required").toBeGreaterThan(0);
  return located.reduce((east, s) => (s.lon > east.lon ? s : east)).station_id;
}

/** Wait for the shell and the first data-bearing paint. */
export async function gotoRoute(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await expect(page.getByRole("navigation", { name: /primary/i })).toBeVisible();
  if (path === "/") await waitForMapIdle(page);
}

/**
 * Wait for MapLibre's own `idle` event, surfaced as `data-map-state` on the map
 * section.
 *
 * The map eases into its bounds on load, and markers are DOM positioned from the
 * projection, so they are genuinely moving for the length of that ease. Clicking
 * mid-flight is a real race, and a fixed sleep would only paper over it - this
 * waits for the map itself to say it has finished.
 */
export async function waitForMapIdle(page: Page): Promise<void> {
  await expect(page.locator("[data-map-state]")).toHaveAttribute("data-map-state", "idle", {
    timeout: 30_000,
  });
}

export async function setTheme(page: Page, theme: "dark" | "light"): Promise<void> {
  await page.getByTestId("theme-switch").selectOption(theme);
  await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
}

export type Role = "public_read" | "researcher" | "operator" | "admin";

/**
 * Switches role through the account menu's dev switcher (TopBar), the same way an
 * operator would - there is no admin key baked into the e2e build, so this is how
 * the suite reaches the Admin screen. The choice persists to localStorage, so it
 * survives the `page.goto` that follows within the same test.
 */
export async function setRole(page: Page, role: Role): Promise<void> {
  const menu = page.getByTestId("account-menu");
  const isOpen = await menu.evaluate((node) => (node.closest("details") as HTMLDetailsElement)?.open);
  if (!isOpen) await menu.click();
  await page.getByTestId("role-switch").selectOption(role);
  await menu.click();
}

/**
 * Scan the current page and fail on any critical violation.
 *
 * Serious/moderate findings are reported in the message but do not fail the build:
 * the phase-3 gate is "zero critical", and a rule that flags a decorative SVG in a
 * chart library should not be able to block a release on its own.
 */
export async function expectNoCriticalA11yViolations(page: Page, context: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const critical = results.violations.filter((violation) => violation.impact === "critical");
  const summary = results.violations
    .map((violation) => `${violation.impact}: ${violation.id} (${violation.nodes.length}) — ${violation.help}`)
    .join("\n");

  expect(critical, `Critical accessibility violations on ${context}:\n${summary}`).toEqual([]);
}

/** Stabilise the viewport before a screenshot: no map animation, no caret. */
export async function settleForSnapshot(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: "reduce" });
  // The map fits its bounds on load; give the easing a moment to finish even with
  // reduced motion, then wait for the network to go quiet.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(300);
}
