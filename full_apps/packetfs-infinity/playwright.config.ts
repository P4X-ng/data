import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  use: {
    headless: true,
    ignoreHTTPSErrors: true,
    baseURL: 'https://127.0.0.1:8811',
    viewport: { width: 1280, height: 800 },
    launchOptions: { slowMo: 300 }
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});