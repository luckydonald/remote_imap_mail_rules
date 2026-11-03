import { expect, test, type Page } from '@playwright/test'

interface Mock {
  requests: { method: string; body: unknown }[]
}

const ACCOUNT = {
  id: '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11',
  name: 'Private',
  host: 'imap.example.com',
  port: 993,
  ssl: true,
  username: 'me@example.com',
  page_size: 50,
  poll_interval: 60,
  has_password: true,
  env_differs: ['password'],
}

/** Stands in for the FastAPI server: a list that follows what is created, edited and deleted. */
const mockServer = async (page: Page, deleteError?: string[]): Promise<Mock> => {
  const mock: Mock = { requests: [] }
  let accounts = [ACCOUNT]
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/accounts**', async (route) => {
    const request = route.request()
    const method = request.method()
    const body = request.postData() ? JSON.parse(request.postData()!) : null
    if (method !== 'GET') mock.requests.push({ method, body })
    if (method === 'POST') {
      accounts = [...accounts, { ...ACCOUNT, ...body, id: 'new-id', env_differs: [] }]
      return route.fulfill({ status: 201, json: accounts.at(-1) })
    }
    if (method === 'PUT') {
      accounts = accounts.map((a) => ({ ...a, ...body, password: undefined, env_differs: [] }))
      return route.fulfill({ json: accounts[0] })
    }
    if (method === 'DELETE') {
      if (deleteError) return route.fulfill({ status: 409, json: { detail: deleteError } })
      accounts = []
      return route.fulfill({ status: 204 })
    }
    return route.fulfill({ json: accounts })
  })
  return mock
}

test('lists accounts with the drift badge, and the database shows as the source', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await expect(page.locator('.notice')).toContainText('the database has no rules yet')
  await page.getByRole('button', { name: 'Accounts' }).click()
  await expect(page.locator('.account')).toContainText('Private')
  await expect(page.locator('.badge.error')).toContainText('differs from env: password')
})

test('adds, edits and deletes an account', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Accounts' }).click()

  await page.getByRole('button', { name: 'Add account' }).click()
  await page.locator('input[name=name]').fill('Work')
  await page.locator('input[name=host]').fill('imap.work.example')
  await page.locator('input[name=username]').fill('me@work.example')
  await page.locator('input[name=password]').fill('secret')
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.account')).toHaveCount(2)
  expect(mock.requests[0]).toMatchObject({ method: 'POST', body: { name: 'Work', password: 'secret' } })

  await page.locator('.account').nth(1).getByRole('button', { name: 'Edit' }).click()
  await expect(page.locator('input[name=password]')).toHaveAttribute('placeholder', 'unchanged')
  await page.locator('input[name=name]').fill('Work 2')
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  expect(mock.requests[1]).toMatchObject({ method: 'PUT', body: { name: 'Work 2', password: null } })

  await page.locator('.account').first().getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Really delete' }).click()
  await expect(page.locator('.message')).toContainText('Deleted.')
  await expect(page.locator('.account')).toHaveCount(0)
})

test('shows why an account cannot be deleted', async ({ page }) => {
  await mockServer(page, ['Still used by the rule: Newsletters'])
  await page.goto('/')
  await page.getByRole('button', { name: 'Accounts' }).click()
  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Really delete' }).click()
  await expect(page.locator('.message')).toContainText('Not deleted: Still used by the rule: Newsletters')
  await expect(page.locator('.account')).toHaveCount(1)
})
