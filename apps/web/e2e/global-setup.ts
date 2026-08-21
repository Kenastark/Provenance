import { chromium, type FullConfig } from "@playwright/test";

/**
 * Seeds `provenance.role` into localStorage before any spec runs, and saves it
 * as a storage state every project loads via `use.storageState`.
 *
 * The sign-in gate (SignInGate) now intercepts a first load with nothing under
 * that key, but the existing suite's specs each navigate straight to a route and
 * expect the dashboard to be there - that behaviour predates the gate and stays
 * unchanged for them. The two dedicated sign-in-screen specs opt back out with
 * `test.use({ storageState: { cookies: [], origins: [] } })` to see the gate for
 * real.
 */
export const STORAGE_STATE_PATH = "e2e/.auth/operator-state.json";

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use?.baseURL ?? "http://localhost:4173";
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });
  // A page must have loaded the origin at least once before localStorage on
  // that origin can be written or captured.
  await page.goto("/");
  await page.evaluate(() => localStorage.setItem("provenance.role", "operator"));
  await page.context().storageState({ path: STORAGE_STATE_PATH });
  await browser.close();
}
