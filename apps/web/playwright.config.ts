import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration.
 *
 * The suite runs against a real browser and a real API: `make demo-data` loads the
 * 18-station demo corpus into TimescaleDB and audits it, the API serves it, and
 * Playwright drives the built dashboard. That is the only way to prove the parts
 * jsdom cannot reach - MapLibre's WebGL canvas, real focus order, real contrast,
 * and the axe-core scan of a fully composed page.
 *
 * `webServer` builds and previews the app rather than running the dev server, so
 * the snapshots are taken of the artefact that would actually ship.
 */

const API_BASE_URL = process.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  timeout: 60_000,
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      // Tight on purpose. The first version of this allowed 2% of pixels to differ,
      // which is roughly 26,000 pixels at this viewport - enough to swallow a whole
      // line of text. A baseline that cannot notice a sentence disappearing is not
      // a gate, it is decoration.
      //
      // `threshold` still absorbs per-pixel antialiasing differences, and the Linux
      // baselines are generated and verified inside one pinned image, so there is
      // no cross-environment noise left to tolerate.
      maxDiffPixelRatio: 0.002,
      threshold: 0.2,
      animations: "disabled",
      caret: "hide",
    },
  },
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      // The quality floor says responsive to 390px, so the responsive checks run at
      // exactly that width rather than at a comfortable one.
      //
      // Chromium at a phone viewport rather than the WebKit iPhone device profile:
      // what is being tested is layout at 390px, and keeping the suite on one
      // engine means one browser download in CI and one set of visual baselines.
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
        deviceScaleFactor: 3,
      },
      testMatch: /responsive\.spec\.ts/,
    },
  ],
  webServer: {
    command: `pnpm build && pnpm preview --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    // Never reuse. A preview server left running from an earlier run serves the
    // build from *that* run, so a fix appears not to work and a visual snapshot is
    // taken of the wrong artefact. Rebuilding costs a few seconds and removes a
    // whole class of confusing failure.
    reuseExistingServer: false,
    timeout: 180_000,
    env: { VITE_API_BASE_URL: API_BASE_URL },
  },
});
