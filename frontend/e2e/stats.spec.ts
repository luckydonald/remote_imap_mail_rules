import { expect, test, type Page } from '@playwright/test'

const mockServer = async (page: Page): Promise<void> => {
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/accounts', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/stats', (route) =>
    route.fulfill({
      json: {
        database: { dialect: 'sqlite', size_bytes: 2097152 },
        tables: {
          accounts: 1,
          rules: 3,
          templates: 0,
          mcp_tokens: 0,
          mail_events: 5,
          mail_events_by_kind: { first_seen: 5 },
        },
        first_event: '2026-11-03T10:00:00Z',
        last_event: '2026-11-04T10:00:00Z',
        data_dir_bytes: 1024,
        watcher: { enabled: true, actions_enabled: false, folders: 2, jobs: 0 },
        started_at: '2026-11-03T09:00:00Z',
        release: 'abc123',
      },
    }),
  )
}

test('the Stats page shows the server and the browser cache', async ({ page }) => {
  await mockServer(page)
  await page.goto('/rules')
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page
    .getByRole('list', { name: 'Settings sections' })
    .getByRole('link', { name: 'Stats' })
    .click()
  await expect(page).toHaveURL(/\/settings\/stats$/)
  await expect(page.getByRole('region', { name: 'Server' })).toContainText('sqlite, 2.0 MB')
  await expect(page.getByRole('region', { name: 'Server' })).toContainText('abc123')
  await expect(page.getByRole('region', { name: 'This browser' })).toContainText('details')
})
