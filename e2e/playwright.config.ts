import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against a live stack: API on :8000 (PostgreSQL), storefront on :3000.
 * In CI that stack is started by .github/workflows/e2e.yml. Locally:
 *   E2E_BASE_URL=http://localhost:3000 E2E_API_URL=http://localhost:8000/api/v1 \
 *   ADMIN_EMAIL=... ADMIN_PASSWORD=... npx playwright test
 */
export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  globalSetup: "./global-setup.ts",
  // One worker: the tests share one database, and several of them create and delete records.
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }], ["json", { outputFile: "test-results/results.json" }]]
    : [["list"]],
  use: {
    // A stuck click or fill fails on its own after 10 s with a "waiting for <locator>" log, instead of
    // running into the 45 s test timeout, which says nothing about where the test was.
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-US",
    timezoneId: "America/Chicago",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
