import { expect, test, type Page } from '@playwright/test'

const ACCOUNT = '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11'

const entry = (uid: number, kind: string, rule: string | null, detail = {}) => ({
  id: `e${uid}-${kind}`,
  account_id: ACCOUNT,
  folder: 'INBOX',
  uid,
  message_id: null,
  kind,
  rule_name: rule,
  detail,
  created_at: '2026-11-03T10:00:00Z',
})

/** Stands in for the log endpoints; the requested queries are recorded. */
const mockServer = async (page: Page): Promise<string[]> => {
  const queries: string[] = []
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/accounts', (route) =>
    route.fulfill({
      json: [
        {
          id: ACCOUNT,
          name: 'Private',
          host: 'imap.example.com',
          port: 993,
          ssl: true,
          username: 'me@example.com',
          page_size: 50,
          poll_interval: 60,
          has_password: true,
          env_differs: [],
        },
      ],
    }),
  )
  await page.route('**/api/log/status', (route) =>
    route.fulfill({
      json: {
        watcher_enabled: true,
        last_run: '2026-11-03T10:05:00Z',
        next_run: '2026-11-03T10:10:00Z',
        push: false,
        last_change: '2026-11-03T10:00:00Z',
        last_action: '2026-11-03T09:00:00Z',
        jobs: [
          {
            kind: 'actions',
            account_id: ACCOUNT,
            folder: 'INBOX',
            uid: 9,
            started_at: '2026-11-03T10:05:00Z',
          },
        ],
      },
    }),
  )
  await page.route('**/api/log/events**', (route) => {
    const url = new URL(route.request().url())
    queries.push(url.search)
    const items =
      url.searchParams.get('q') === 'nothing'
        ? []
        : [entry(2, 'rule_match', 'invoices', { match_kind: 'new' }), entry(1, 'first_seen', null)]
    return route.fulfill({ json: { items, next: null } })
  })
  return queries
}

test('shows the status box and the log, filters and links to the mail', async ({ page }) => {
  const queries = await mockServer(page)
  await page.goto('/settings/log')
  await expect(page.getByRole('heading', { name: 'Action log' })).toBeVisible()
  await expect(page.getByLabel('Watcher status')).toContainText('Watcher last ran')
  await expect(page.locator('[data-test=last-action]')).not.toHaveText('never')
  await expect(page.locator('[data-test=jobs] li')).toContainText('Running rules on mail')
  await expect(page.locator('.entries li')).toHaveCount(2)
  await expect(page.locator('.entries li').first()).toContainText(
    'Matched the rule "invoices" (new)',
  )
  await expect(page.locator('.entries li').first().locator('.where')).toHaveText(
    'Private · INBOX · 2',
  )
  // The rule file buttons do not belong on this screen.
  await expect(page.getByRole('button', { name: 'Download' })).toHaveCount(0)

  await page.getByLabel('Search').fill('nothing')
  await expect(page.getByText('Nothing matches these filters.')).toBeVisible()
  expect(queries.at(-1)).toContain('q=nothing')
  await expect(page).toHaveURL(/\/settings\/log\?q=nothing/)

  await page.getByRole('button', { name: 'Clear filters' }).click()
  await expect(page.locator('.entries li')).toHaveCount(2)
  await page.getByLabel('Rule actions').check()
  await expect.poll(() => queries.at(-1)).toContain('kind=action')
})

test('a filtered link opens with the filters set', async ({ page }) => {
  const queries = await mockServer(page)
  await page.goto('/settings/log?kind=user_action&folder=Archive')
  await expect(page.getByLabel('Your actions')).toBeChecked()
  await expect(page.getByLabel('Folder')).toHaveValue('Archive')
  expect(queries[0]).toContain('kind=user_action')
  expect(queries[0]).toContain('folder=Archive')
})

test('the Log link is in the settings navigation', async ({ page }) => {
  await mockServer(page)
  await page.goto('/rules')
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page
    .getByRole('list', { name: 'Settings sections' })
    .getByRole('link', { name: 'Action log' })
    .click()
  await expect(page).toHaveURL(/\/settings\/log$/)
})

test('the old /log path redirects and keeps the filters', async ({ page }) => {
  await mockServer(page)
  await page.goto('/log?kind=user_action')
  await expect(page).toHaveURL(/\/settings\/log\?kind=user_action/)
})

test('reads the accounts once, they are the store’s shared list', async ({ page }) => {
  await mockServer(page)
  let requests = 0
  await page.route('**/api/accounts', (route) => {
    requests += 1
    return route.fallback()
  })
  await page.goto('/settings/log')
  await expect(page.getByLabel('Account')).toContainText('Private')
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page.getByRole('link', { name: 'Action log' }).click()
  await expect(page.locator('.entries li')).toHaveCount(2)
  await expect(page.getByLabel('Account')).toContainText('Private')
  expect(requests).toBe(1)
})
