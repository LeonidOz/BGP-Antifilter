import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(directory, "../.cache/ms-playwright");

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  globalTeardown: "./e2e/teardown.js",
  timeout: 30000,
  use: {baseURL: "http://127.0.0.1:18761", locale: "en-US", trace: "retain-on-failure", screenshot: "only-on-failure"},
  projects: [
    {name: "desktop", use: {...devices["Desktop Chrome"]}},
    {name: "mobile", use: {...devices["Pixel 7"]}},
  ],
  webServer: {command: "python ../tests/browser_server.py", url: "http://127.0.0.1:18761/api/session", reuseExistingServer: false, timeout: 30000},
});
