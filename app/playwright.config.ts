import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PREVIEW_PORT || 4181);

export default defineConfig({
  testDir: "tests/e2e",
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: `http://127.0.0.1:${port}/` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Serves the existing build; run `npm run build` first.
  webServer: {
    command: "npm run preview",
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: !process.env.CI,
  },
});
