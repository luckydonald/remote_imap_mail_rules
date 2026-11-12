import { expect, test, type Page } from '@playwright/test'
import { ACCOUNT_ID, logIn, mockServer as mockMailServer } from './mail-mock'

/** The accounts live under Settings: the top bar link, then the section link. */
const openAccounts = async (page: Page): Promise<void> => {
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page
    .getByRole('list', { name: 'Settings sections' })
    .getByRole('link', { name: 'Accounts' })
    .click()
  await expect(page).toHaveURL(/\/settings\/accounts$/)
}

interface Mock {
  requests: { method: string; body: unknown }[]
  /** The bodies of the login checks. */
  checks: unknown[]
  /** The answer of the login check, ok when unset. */
  check?: { ok: boolean; kind: string; message: string }
}

const ACCOUNT: Record<string, unknown> = {
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
  auth_updated_at: '2026-11-01T10:00:00Z',
  auth_failed_at: null,
  auth_fail_count: 0,
  auth_ok_at: null,
  auth_last_error: null,
  needs_check: false,
}

/** Stands in for the FastAPI server: a list that follows what is created, edited and deleted. */
const mockServer = async (page: Page, deleteError?: string[], account = ACCOUNT): Promise<Mock> => {
  const mock: Mock = { requests: [], checks: [] }
  let accounts = [account]
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/accounts**', async (route) => {
    const request = route.request()
    const method = request.method()
    const body = request.postData() ? JSON.parse(request.postData()!) : null
    if (request.url().endsWith('/api/accounts/check')) {
      mock.checks.push(body)
      return route.fulfill({ json: mock.check ?? { ok: true, kind: 'ok', message: 'Login works.' } })
    }
    if (method !== 'GET') mock.requests.push({ method, body })
    if (method === 'POST') {
      accounts = [...accounts, { ...ACCOUNT, ...body, id: '22222222-2222-4333-8444-555555555555', env_differs: [] }]
      return route.fulfill({ status: 201, json: accounts.at(-1) })
    }
    if (method === 'PUT') {
      const target = request.url().split('/').pop()
      accounts = accounts.map((a) =>
        a.id === target ? { ...a, ...body, id: body.id ?? a.id, password: undefined, env_differs: [] } : a,
      )
      return route.fulfill({ json: accounts.find((a) => a.id === (body.id ?? target)) })
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
  await openAccounts(page)
  await expect(page.locator('.account')).toContainText('Private')
  await expect(page.locator('.badge.error')).toContainText('differs from env: password')
})

test('flags an account whose login was rejected, with its history', async ({ page }) => {
  await mockServer(page, undefined, {
    ...ACCOUNT,
    env_differs: [],
    auth_failed_at: '2026-11-06T19:44:17Z',
    auth_fail_count: 3,
    auth_ok_at: '2026-11-05T08:00:00Z',
    auth_last_error: 'authentication failed',
    needs_check: true,
  })
  await page.goto('/')
  await openAccounts(page)
  await expect(page.locator('.badge.needs-check')).toContainText('Please check')
  await expect(page.locator('.login-history')).toContainText('3× since the credentials were set')
  await expect(page.locator('.login-history')).toContainText('authentication failed')
})

test('adds, edits and deletes an account', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await openAccounts(page)

  await page.getByRole('button', { name: 'Add account' }).click()
  await page.locator('input[name=name]').fill('Work')
  await page.locator('input[name=host]').fill('imap.work.example')
  await page.locator('input[name=username]').fill('me@work.example')
  await page.locator('input[name=password]').fill('secret')
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.account')).toHaveCount(2)
  expect(mock.requests[0]).toMatchObject({ method: 'POST', body: { name: 'Work', id: null, password: 'secret' } })

  await page.locator('.account').nth(1).getByRole('button', { name: 'Edit' }).click()
  await expect(page.locator('input[name=password]')).toHaveAttribute('placeholder', 'unchanged')
  await page.locator('input[name=name]').fill('Work 2')
  await page.locator('input[name=id]').fill('11111111-2222-4333-8444-555555555555')
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  expect(mock.requests[1]).toMatchObject({ method: 'PUT', body: { name: 'Work 2', id: '11111111-2222-4333-8444-555555555555', password: null } })

  await page.locator('.account').first().getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Really delete' }).click()
  await expect(page.locator('.message')).toContainText('Deleted.')
  await expect(page.locator('.account')).toHaveCount(0)
})

test('checks the login on Save, offers Save anyway when it fails, and skips the check for a rename', async ({ page }) => {
  const mock = await mockServer(page)
  mock.check = { ok: false, kind: 'rejected', message: 'authentication failed' }
  await page.goto('/')
  await openAccounts(page)

  await page.getByRole('button', { name: 'Add account' }).click()
  await page.locator('input[name=name]').fill('Work')
  await page.locator('input[name=host]').fill('imap.work.example')
  await page.locator('input[name=username]').fill('me@work.example')
  await page.locator('input[name=password]').fill('wrong')
  const form = page.locator('.account-form')
  await form.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(form.locator('.check-result.error')).toContainText('authentication failed')
  expect(mock.checks).toHaveLength(1)
  expect(mock.requests).toHaveLength(0)

  await form.getByRole('button', { name: 'Save anyway' }).click()
  await expect(page.locator('.account')).toHaveCount(2)
  expect(mock.requests[0]).toMatchObject({ method: 'POST', body: { name: 'Work', password: 'wrong' } })
  expect(mock.checks).toHaveLength(1)

  // A rename changes nothing about the login, so no check.
  await page.locator('.account').first().getByRole('button', { name: 'Edit' }).click()
  await page.locator('input[name=name]').fill('Renamed')
  await form.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.locator('.account').first()).toContainText('Renamed')
  expect(mock.checks).toHaveLength(1)
})

test('Test connection shows the result without saving', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await openAccounts(page)
  await page.locator('.account').first().getByRole('button', { name: 'Edit' }).click()
  await page.getByRole('button', { name: 'Test connection' }).click()
  await expect(page.locator('.check-result.ok')).toContainText('Login works.')
  expect(mock.checks).toMatchObject([{ id: ACCOUNT.id, password: null }])
  expect(mock.requests).toHaveLength(0)
  await expect(page.getByRole('button', { name: 'Save anyway' })).toHaveCount(0)
})

test('shows why an account cannot be deleted', async ({ page }) => {
  await mockServer(page, ['Still used by the rule: Newsletters'])
  await page.goto('/')
  await openAccounts(page)
  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Really delete' }).click()
  await expect(page.locator('.message')).toContainText('Not deleted: Still used by the rule: Newsletters')
  await expect(page.locator('.account')).toHaveCount(1)
})

/** The mail mock plus an account endpoint that follows creates and id changes; later routes win over the mock's own. */
const mockMailWithAccounts = async (page: Page): Promise<void> => {
  await mockMailServer(page)
  let accounts = [{ ...ACCOUNT, id: ACCOUNT_ID, env_differs: [] as string[] }]
  await page.route('**/api/accounts**', async (route) => {
    const request = route.request()
    const body = request.postData() ? JSON.parse(request.postData()!) : null
    if (request.url().endsWith('/api/accounts/check')) {
      return route.fulfill({ json: { ok: true, kind: 'ok', message: 'Login works.' } })
    }
    if (request.method() === 'POST') {
      accounts = [...accounts, { ...ACCOUNT, ...body, id: '22222222-2222-4333-8444-555555555555', env_differs: [] }]
      return route.fulfill({ status: 201, json: accounts.at(-1) })
    }
    if (request.method() === 'PUT') {
      const target = request.url().split('/').pop()
      accounts = accounts.map((a) => (a.id === target ? { ...a, ...body, id: body.id ?? a.id } : a))
      return route.fulfill({ json: accounts.find((a) => a.id === (body.id ?? target)) })
    }
    return route.fulfill({ json: accounts })
  })
}

test('an added account shows in the mail screen picker', async ({ page }) => {
  await mockMailWithAccounts(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await expect(page.locator('.account-pick')).toHaveCount(0)

  await openAccounts(page)
  await page.getByRole('button', { name: 'Add account' }).click()
  await page.locator('input[name=name]').fill('Work')
  await page.locator('input[name=host]').fill('imap.work.example')
  await page.locator('input[name=username]').fill('me@work.example')
  await page.locator('input[name=password]').fill('secret')
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.account')).toHaveCount(2)

  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.account-pick option')).toHaveCount(2)
})

test('the open mail account follows a changed id', async ({ page }) => {
  const renamed = '11111111-2222-4333-8444-555555555555'
  await mockMailWithAccounts(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page).toHaveURL(new RegExp(ACCOUNT_ID))

  await openAccounts(page)
  await page.locator('.account').first().getByRole('button', { name: 'Edit' }).click()
  await page.locator('input[name=id]').fill(renamed)
  await page.locator('.account-form').getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.account .hint')).toHaveText(renamed)

  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`${renamed}/INBOX/3`))
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
})
