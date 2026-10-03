import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs against a production build (`next build && next start`). The
 * engine is mocked with page.route at ENGINE; the build bakes that origin
 * into the page and its CSP, so the CSP's connect-src is exercised too.
 */
const PORT = Number(process.env.E2E_PORT ?? 3100);
const ENGINE = "http://127.0.0.1:8099";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0, // a flaky test is a bug to root-cause, never a retry to hide
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 900 },
  },
  projects: [{ name: "chromium" }],
  webServer: {
    command: `npx next build && npx next start --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    timeout: 240_000,
    reuseExistingServer: false, // always test a fresh build of the current code
    env: { NEXT_PUBLIC_ENGINE_URL: ENGINE, NEXT_TELEMETRY_DISABLED: "1" },
  },
});
