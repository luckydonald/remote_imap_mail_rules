import { expect, test, type Page } from '@playwright/test'

const ACCOUNT_ID = '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11'

const FOLDERS = [
  {
    name: 'INBOX',
    display_name: 'INBOX',
    delimiter: '/',
    special_use: 'inbox',
    selectable: true,
    messages: 3,
    unseen: 2,
  },
  {
    name: 'Sent',
    display_name: 'Sent',
    delimiter: '/',
    special_use: 'sent',
    selectable: true,
    messages: 1,
    unseen: 0,
  },
]

const summary = (uid: number, seen = false) => ({
  uid,
  sender: { name: `Sender ${uid}`, address: `s${uid}@example.com` },
  subject: `Subject ${uid}`,
  date: '2026-10-01T08:30:00Z',
  seen,
  flagged: false,
  answered: false,
  has_attachments: uid === 3,
  size: 100,
})

const DETAIL = {
  ...summary(3),
  to: [{ name: 'Me', address: 'me@example.com' }],
  cc: [],
  reply_to: [],
  message_id: '<m@x>',
  text: 'plain text',
  html: '<p>Hello <b>rich</b> world</p>',
  attachments: [
    {
      part: '2',
      filename: 'report.pdf',
      mime_type: 'application/pdf',
      size: 2048,
      inline: false,
      content_id: null,
      url: `/api/mail/accounts/${ACCOUNT_ID}/messages/3/parts/2?folder=INBOX`,
    },
  ],
}

/** The server: needs a login first, then serves one account with an inbox of three mails in two pages. */
const mockServer = async (page: Page, wrongPassword = false): Promise<string[]> => {
  const calls: string[] = []
  let loggedIn = false
  await page.route('**/api/editor/config', (route) =>
    loggedIn
      ? route.fulfill({
          json: { mode: 'server', source: 'database', file_name: null, exists: false },
        })
      : route.fulfill({ status: 401, json: { detail: 'Not logged in.' } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/auth/login', (route) => {
    calls.push(`login ${route.request().postData()}`)
    if (wrongPassword)
      return route.fulfill({ status: 401, json: { detail: 'Wrong username or password.' } })
    loggedIn = true
    return route.fulfill({ status: 204 })
  })
  await page.route('**/api/auth/logout', (route) => {
    calls.push('logout')
    loggedIn = false
    return route.fulfill({ status: 204 })
  })
  await page.route('**/api/accounts', (route) =>
    route.fulfill({
      json: [
        {
          id: ACCOUNT_ID,
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
  await page.route('**/api/mail/**', (route) => {
    const url = new URL(route.request().url())
    calls.push(url.pathname.replace(`/api/mail/accounts/${ACCOUNT_ID}`, '') + url.search)
    if (url.pathname.endsWith('/folders')) return route.fulfill({ json: FOLDERS })
    if (url.pathname.endsWith('/messages') && url.searchParams.has('before_uid'))
      return route.fulfill({
        json: { messages: [summary(1, true)], total: 3, next_before_uid: null },
      })
    if (url.pathname.endsWith('/messages'))
      return route.fulfill({
        json: { messages: [summary(3), summary(2, true)], total: 3, next_before_uid: 2 },
      })
    return route.fulfill({ json: DETAIL })
  })
  return calls
}

const logIn = async (page: Page): Promise<void> => {
  await page.getByLabel('Username').fill('me@example.com')
  await page.getByLabel('Password').fill('secret')
  await page.getByRole('button', { name: 'Log in' }).click()
}

test('asks for a login, then browses folders, pages and reads a message', async ({ page }) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await logIn(page)
  expect(calls[0]).toContain('"username":"me@example.com"')
  await page.getByRole('button', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-folders .folder')).toHaveCount(2)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('INBOX')
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await expect(page.locator('.row-mail.unread')).toHaveCount(1)
  await page.getByRole('button', { name: 'Load older messages' }).click()
  await expect(page.locator('.row-mail')).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Load older messages' })).toHaveCount(0)
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page.locator('.mail-message .meta')).toContainText('Sender 3 <s3@example.com>')
  await expect(page.locator('.attachments a')).toContainText('report.pdf')
  await expect(page.frameLocator('iframe.body-frame').locator('b')).toHaveText('rich')
  await expect(page.locator('iframe.body-frame')).toHaveAttribute(
    'sandbox',
    /^((?!allow-scripts).)*$/,
  )
})

test('shows the server message for wrong credentials', async ({ page }) => {
  await mockServer(page, true)
  await page.goto('/')
  await logIn(page)
  await expect(page.getByRole('alert')).toHaveText('Wrong username or password.')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
})

test('logs out back to the login', async ({ page }) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  expect(calls).toContain('logout')
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 800 } })

  test('shows one pane at a time and navigates back', async ({ page }) => {
    await mockServer(page)
    await page.goto('/')
    await logIn(page)
    await page.getByRole('button', { name: 'Mail', exact: true }).click()
    await expect(page.locator('.mail-list')).toBeVisible()
    await expect(page.locator('.mail-folders')).toBeHidden()
    await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
    await expect(page.locator('.mail-message')).toBeVisible()
    await expect(page.locator('.mail-list')).toBeHidden()
    await page.getByRole('button', { name: '‹ Messages' }).click()
    await expect(page.locator('.mail-list')).toBeVisible()
    await page.getByRole('button', { name: '‹ Folders' }).click()
    await expect(page.locator('.mail-folders')).toBeVisible()
  })
})

test('shows a loading spinner while the list is fetched', async ({ page }) => {
  await mockServer(page)
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/mail/**/messages*', async (route) => {
    await gate
    await route.fallback()
  })
  await page.goto('/')
  await logIn(page)
  await page.getByRole('button', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await expect(page.locator('.mail-spinner')).toHaveCount(0)
})
