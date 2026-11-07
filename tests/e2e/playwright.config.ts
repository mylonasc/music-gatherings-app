import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Shared seeded library: serialize mutation journeys across devices.
  reporter: [["list"], ["html", { open: "never" }], ["./gallery-reporter.ts"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    reducedMotion: "reduce",
  },
  projects: [
    { name: "setup", testMatch: /.*\.setup\.ts/ },
    {
      name: "pixel-compact",
      dependencies: ["setup"],
      use: { ...devices["Pixel 5"] },
    },
    {
      name: "iphone-small",
      dependencies: ["setup"],
      use: { ...devices["iPhone SE"] },
    },
    {
      name: "chromium-desktop",
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 720 } },
    },
    {
      name: "chromium-mobile",
      dependencies: ["setup"],
      use: { ...devices["Pixel 7"] },
    },
    {
      name: "webkit-mobile",
      dependencies: ["setup"],
      use: { ...devices["iPhone 14"] },
    },
    {
      name: "iphone-large",
      dependencies: ["setup"],
      use: { ...devices["iPhone 14 Pro Max"] },
    },
  ],
});
