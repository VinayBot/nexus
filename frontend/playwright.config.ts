import { createHmac } from "node:crypto";
import { defineConfig } from "@playwright/test";

const API = "http://127.0.0.1:8011";
const UI = "http://localhost:3011";

/** e2e runs with auth ON. A fixed secret lets us sign the owner's session token here. */
const SECRET = "e2e-only-secret-key-0123456789abcdef0123456789";
const b64 = (v: object | Buffer) => (Buffer.isBuffer(v) ? v : Buffer.from(JSON.stringify(v))).toString("base64url");
function sessionToken(sub: string, role: string): string {
  const now = Math.floor(Date.now() / 1000);
  const body = `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub, role, iat: now, exp: now + 86_400 })}`;
  return `${body}.${b64(createHmac("sha256", SECRET).update(body).digest())}`;
}
export const OWNER_TOKEN = sessionToken("owner", "owner");

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
  use: {
    baseURL: UI,
    trace: "retain-on-failure",
    viewport: { width: 1500, height: 950 },
    // signed in as the seeded owner: API calls from tests and the app's own session
    extraHTTPHeaders: { Authorization: `Bearer ${OWNER_TOKEN}` },
    storageState: {
      cookies: [],
      origins: [{ origin: UI, localStorage: [{ name: "nexus-token", value: OWNER_TOKEN }] }],
    },
  },
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
        NEXUS_PUBLIC_URL: API,
        NEXUS_AUTH_ENABLED: "true",
        NEXUS_MISSIONS_PER_MINUTE: "1000", // the suite starts many missions quickly
        NEXUS_SECRET_KEY: SECRET,
        NEXUS_BOOTSTRAP_USERS: "owner:owner-pass-123:owner,viewer:viewer-pass-123:viewer",
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
