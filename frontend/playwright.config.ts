import { defineConfig, devices } from '@playwright/test'

const PORT = 5199

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    // Safari on an iPad Pro 12.9" in landscape (1366 x 1024), the engine and size a menu was once clipped on.
    {
      name: 'webkit-ipad',
      testMatch: 'mail.spec.ts',
      use: { ...devices['iPad Pro 11 landscape'], viewport: { width: 1366, height: 1024 } },
    },
  ],
  webServer: {
    // Nothing listens on port 9, so a server running on 8000 cannot change what the tests see.
    command: `API_PROXY=http://127.0.0.1:9 yarn vite --port ${PORT} --strictPort`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
})
