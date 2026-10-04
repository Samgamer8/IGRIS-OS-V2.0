import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 90000,
  workers: 1,
  use: { channel: 'msedge', headless: true, viewport: { width: 1440, height: 900 },
    launchOptions: { args: ['--enable-unsafe-swiftshader'] }, screenshot: 'only-on-failure' },
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5179 --strictPort',
    url: 'http://127.0.0.1:5179', reuseExistingServer: true, timeout: 30000 },
});