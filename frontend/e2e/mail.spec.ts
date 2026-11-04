import { expect, test } from '@playwright/test'
import { ACCOUNT_ID, logIn, mockServer } from './mail-mock'

test('asks for a login, then browses folders, pages and reads a message', async ({ page }) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await logIn(page)
  expect(calls[0]).toContain('"username":"me@example.com"')
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await expect(page.locator('.mail-log li')).toHaveCount(2)
  await expect(page.locator('.mail-log li').first()).toContainText('First seen')
  await expect(page.locator('.mail-log li').nth(1)).toContainText(
    'Matched the rule "invoices" (new)',
  )
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
    await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await expect(page.locator('.mail-spinner')).toHaveCount(0)
})

test('shows a loading spinner in the folder pane while the folders are fetched', async ({
  page,
}) => {
  await mockServer(page)
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/mail/**/folders', async (route) => {
    await gate
    await route.fallback()
  })
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-folders .mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.mail-folders .folder')).toHaveCount(2)
  await expect(page.locator('.mail-folders .mail-spinner')).toHaveCount(0)
})

test('shows a loading spinner while the message is fetched', async ({ page }) => {
  await mockServer(page)
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route('**/api/mail/**/messages/3*', async (route) => {
    await gate
    await route.fallback()
  })
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message .mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page.locator('.mail-message .mail-spinner')).toHaveCount(0)
})

test('the screens have their own URLs and the back button returns to the previous one', async ({
  page,
}) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await expect(page).toHaveURL(/\/rules$/)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-folders .folder')).toHaveCount(2)
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await page.goBack()
  await expect(page).toHaveURL(/\/rules$/)
  await expect(page.locator('.mail-folders')).toHaveCount(0)
})

test('the mail browser keeps account, folder and message in the URL', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX/3`)
  await page.locator('.mail-folders .folder', { hasText: 'Sent' }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/Sent`)
  // The back button walks the places in reverse.
  await page.goBack()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX/3`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('INBOX')
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await page.goBack()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await expect(page.locator('.mail-message h2')).toHaveCount(0)
})

test('opens a mail from its URL', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.goto(`/mail/${ACCOUNT_ID}/Sent/3`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('Sent')
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/Sent/3`)
  // A URL with only the account falls back to the inbox.
  await page.goto(`/mail/${ACCOUNT_ID}`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('INBOX')
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
})


const MOVE_RULES = `rules:
  - name: sent copy
    locations:
      - account_id: ${ACCOUNT_ID}
        folder: INBOX
    when:
      type: bool
      field: seen
    actions:
      - type: move
        folder: Sent
`

async function openThird(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
}

test('marks the open mail unread and read again', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.getByRole('button', { name: 'Mark read' }).click()
  await expect(page.getByRole('button', { name: 'Mark unread' })).toBeVisible()
  await expect(page.locator('.row-mail.active')).not.toHaveClass(/unread/)
  expect(calls).toContain('body {"add":["\\\\Seen"],"remove":[]}')
})

test('moves the mail to a destination of the rules', async ({ page }) => {
  const calls = await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await page.getByRole('menuitem', { name: 'Sent' }).click()
  expect(calls).toContain('body {"folder":"Sent"}')
  await expect(page.locator('.row-mail')).toHaveCount(1)
})

test('moves the mail to a folder picked in the tree under More', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await page.getByRole('menuitem', { name: 'More …' }).click()
  await page.getByRole('treeitem', { name: /Sent/ }).click()
  expect(calls).toContain('body {"folder":"Sent"}')
})

test('shows the text version and remembers the choice', async ({ page }) => {
  await mockServer(page)
  await openThird(page)
  await expect(page.locator('iframe.body-frame')).toBeVisible()
  await page.getByRole('radio', { name: 'Text' }).click()
  await expect(page.locator('pre.body-text')).toHaveText('plain text')
  await page.reload()
  await expect(page.getByRole('radio', { name: 'Text' })).toHaveAttribute('aria-checked', 'true')
})

test('lists the blocked images and loads them on request', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.locator('.blocked-images summary').click()
  await expect(page.locator('.blocked-images a')).toHaveCount(2)
  await expect(page.locator('.blocked-images a').first()).toHaveText('https://t.example/a.gif')
  await page.getByRole('button', { name: 'Load remote images' }).click()
  await expect(page.locator('.blocked-images')).toHaveCount(0)
  expect(calls.some((call) => call.includes('remote_images=true'))).toBe(true)
})

test('the header and the body scroll as one', async ({ page }) => {
  await mockServer(page)
  await openThird(page)
  const frame = page.locator('iframe.body-frame')
  const sizes = await frame.evaluate((element: HTMLIFrameElement) => ({
    frame: element.clientHeight,
    content: element.contentDocument?.documentElement.scrollHeight ?? 0,
  }))
  // The page scrolls, not the frame: its content fits into it.
  expect(sizes.content).toBeLessThanOrEqual(sizes.frame)
})

test('the rule button starts a rule from the mail', async ({ page }) => {
  await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'New rule from this mail' }).click()
  await expect(page).toHaveURL(/\/rules\/1$/)
})
