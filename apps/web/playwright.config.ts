import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    headless: true,
    actionTimeout: 10_000,
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'pnpm exec next dev --port 3000',
    cwd: __dirname,
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    env: {
      NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET || 'test-secret',
      NEXTAUTH_URL: process.env.NEXTAUTH_URL || 'http://localhost:3000',
      NEXTAUTH_ALLOW_TEST_CREDENTIALS: 'true',
      NEXTAUTH_TEST_USER: process.env.NEXTAUTH_TEST_USER || 'e2e@test.local',
      NEXTAUTH_TEST_PASSWORD: process.env.NEXTAUTH_TEST_PASSWORD || 'E2EPassw0rd!',
      AUTH_SECRET: process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || 'test-secret',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
