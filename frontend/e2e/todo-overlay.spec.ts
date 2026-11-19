import { expect, test, type Page } from '@playwright/test'
import { logIn, mockServer } from './mail-mock'

type OverlayConfig = { url: string | null; token: string | null } | null

async function mockConfig(page: Page, todo_overlay: OverlayConfig): Promise<void> {
  await page.route('**/api/public/client-config', (route) =>
    route.fulfill({ json: { sentry: null, todo_overlay } }),
  )
}

const emptyConfig = { url: null, token: null }
const launcher = (page: Page) => page.getByRole('button', { name: 'Quick add', exact: true })

test('shows a single launcher on the login screen, rules and settings', async ({ page }) => {
  await mockServer(page)
  await mockConfig(page, emptyConfig)
  await page.goto('/rules')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await expect(launcher(page)).toBeVisible()
  await logIn(page)
  await expect(page.getByRole('link', { name: 'Rules', exact: true })).toBeVisible()
  await expect(launcher(page)).toBeVisible()
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await expect(page).toHaveURL(/\/settings$/)
  await expect(launcher(page)).toBeVisible()
})

test('omits the launcher when the deployment disables it', async ({ page }) => {
  await mockServer(page)
  await mockConfig(page, null)
  const config = page.waitForResponse('**/api/public/client-config')
  await page.goto('/rules')
  await config
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await expect(launcher(page)).toHaveCount(0)
  await logIn(page)
  await expect(launcher(page)).toHaveCount(0)
})

test('opens editable settings when URL and token are unset', async ({ page }) => {
  await mockConfig(page, emptyConfig)
  await page.goto('/rules')
  await launcher(page).click()
  const settings = page.getByRole('dialog', { name: 'Settings' })
  await expect(settings.getByLabel('Server URL')).toBeEditable()
  await expect(settings.getByLabel('Embed key')).toBeEditable()
})

test('opens the settings gear with values remembered in this browser', async ({ page }) => {
  await mockConfig(page, emptyConfig)
  await page.route('https://todos.example.test/api/embed/**', (route) =>
    route.fulfill({ json: [], headers: { 'Access-Control-Allow-Origin': '*' } }),
  )
  const saved = { url: 'https://todos.example.test', token: 'browser-embed-key' }
  await page.addInitScript((values) => {
    localStorage.setItem('sync-todo-overlay', JSON.stringify(values))
  }, saved)
  await page.goto('/rules')
  await launcher(page).click()
  await page
    .getByRole('dialog', { name: 'Quick add' })
    .getByRole('button', { name: 'Settings' })
    .click()
  const settings = page.getByRole('dialog', { name: 'Settings' })
  await expect(settings.getByLabel('Server URL')).toHaveValue(saved.url)
  await expect(settings.getByLabel('Embed key')).toHaveValue(saved.token)
  await expect(settings.getByLabel('Server URL')).toBeEditable()
  await expect(settings.getByLabel('Embed key')).toBeEditable()
})

for (const viewport of [
  { width: 1280, height: 720 },
  { width: 375, height: 700 },
]) {
  test(`keeps the mail controls usable at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await mockServer(page)
    await mockConfig(page, emptyConfig)
    await page.goto('/mail')
    await logIn(page)
    await expect(launcher(page)).toBeVisible()
    await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
    await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
    const toolbar = await page.locator('.mail-message .toolbar').boundingBox()
    const button = await launcher(page).boundingBox()
    expect(toolbar).not.toBeNull()
    expect(button).not.toBeNull()
    expect(toolbar!.y + toolbar!.height).toBeLessThan(button!.y)
    await launcher(page).click()
    await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible()
  })
}
