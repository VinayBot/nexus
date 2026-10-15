import { defineConfig } from "@playwright/test";

const API = "http://127.0.0.1:8011";

/**
 * End-to-end tests run against a fresh backend in Simulation mode (scripted model,
 * everything else real) and a separate Next dev server, so they never touch your
 * dev data or your running servers.
 */
export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3011", trace: "retain-on-failure", viewport: { width: 1500, height: 950 } },
  webServer: [
    {
      command: "cd ../backend && rm -rf /tmp/nexus-e2e && uv run uvicorn nexus.api.app:app --port 8011",
      url: `${API}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXUS_LLM_PROVIDER: "simulation",
        NEXUS_DATA_DIR: "/tmp/nexus-e2e",
        NEXUS_DEMO_AUTOSTART: "false",
        NEXUS_SANDBOX_BACKEND: "local",
        NEXUS_SMTP_PORT: "9",
        NEXUS_CORS_ORIGINS: '["http://localhost:3011","http://127.0.0.1:3011"]',
      },
    },
    {
      command: "pnpm exec next dev --turbopack -p 3011",
      url: "http://localhost:3011/missions",
      reuseExistingServer: false,
      timeout: 180_000,
      env: { NEXT_PUBLIC_API_URL: API, NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
