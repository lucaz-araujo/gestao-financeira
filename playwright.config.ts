import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: 'frontend/e2e', fullyParallel: false, workers: 1, timeout: 90000,
  use: { baseURL: process.env.E2E_BASE_URL, headless: true, actionTimeout: 10000, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: 'list' });