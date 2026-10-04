import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testMatch: '**/*.spec.js', workers: 1, timeout: 30000,
  use: { channel: 'msedge', headless: true, viewport: { width: 1440, height: 960 },
    screenshot: 'only-on-failure', acceptDownloads: true },
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5185 --strictPort',
    url: 'http://127.0.0.1:5185', reuseExistingServer: true },
});