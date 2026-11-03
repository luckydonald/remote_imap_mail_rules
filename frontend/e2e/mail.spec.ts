import { expect, test } from '@playwright/test'
import { logIn, mockServer } from './mail-mock'

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
  await page.getByRole('button', { name: 'Mail', exact: true }).click()
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
  await page.getByRole('button', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message .mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page.locator('.mail-message .mail-spinner')).toHaveCount(0)
})
