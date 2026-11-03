import { expect, test, type Page } from '@playwright/test'
import { ACCOUNT_ID, logIn, mockServer } from './mail-mock'

const RULES = `rules:
  - name: Newsletter
    locations:
      - account_id: ${ACCOUNT_ID}
    when:
      type: text
      field: subject
      operator: contains
      value: ""
`

const openRule = async (page: Page): Promise<void> => {
  await mockServer(page, false, RULES)
  await page.goto('/')
  await logIn(page)
  await page.locator('.rule-list li .select').first().click()
  await expect(page.locator('.rule-editor')).toBeVisible()
}

const inputValues = (page: Page) =>
  page.locator('.rule-editor input').evaluateAll((items) => items.map((i) => (i as HTMLInputElement).value))

const openMail = async (page: Page): Promise<void> => {
  await page.getByRole('button', { name: 'Example mail' }).click()
  await page.locator('.mail-panel .row-mail').first().click()
  await expect(page.locator('.mail-panel .mail-message .subject')).toHaveText('Subject 3')
}

test('fills a condition from the mail beside the editor and undoes it', async ({ page }) => {
  await openRule(page)
  await page.locator('.fill-from-mail').first().click()
  // No mail yet, so the button only opens the panel.
  await expect(page.locator('.mail-panel')).toBeVisible()
  await page.locator('.mail-panel .row-mail').first().click()
  await expect(page.locator('.mail-panel .mail-message .subject')).toHaveText('Subject 3')
  await page.locator('.rule-editor .fill-from-mail').first().click()
  await expect.poll(() => inputValues(page)).toContain('Subject 3')
  await page.getByTitle('Undo').click()
  await expect.poll(() => inputValues(page)).not.toContain('Subject 3')
})

test('adds a condition from the mail with the chosen part of the address', async ({ page }) => {
  await openRule(page)
  await openMail(page)
  await page.getByLabel('Field', { exact: true }).selectOption('from')
  await page.getByLabel('Part of the address').selectOption('name')
  await page.locator('.add-condition').click()
  await expect.poll(() => inputValues(page)).toContain('Sender 3')
  await expect(page.locator('.rule-editor .node-all')).toHaveCount(1)
})

test('keeps the open mail after a reload', async ({ page }) => {
  await openRule(page)
  await openMail(page)
  await page.reload()
  await page.locator('.rule-list li .select').first().click()
  await page.locator('.rule-editor .fill-from-mail').first().click()
  await expect.poll(() => inputValues(page)).toContain('Subject 3')
})

test('shows the mail as a subpage on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 800 })
  await openRule(page)
  await page.getByRole('button', { name: 'Example mail' }).click()
  await expect(page.locator('.mail-panel')).toBeVisible()
  await expect(page.locator('.rule-list')).toBeHidden()
  await page.getByRole('button', { name: '‹ Rules' }).click()
  await expect(page.locator('.rule-list')).toBeVisible()
  await expect(page.locator('.mail-panel')).toHaveCount(0)
})
