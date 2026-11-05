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

/** Logs in and waits until the server's rules replaced the editor's default file, else a click on the rule list can hit a rule that is about to vanish. */
const logInAndLoad = async (page: Page): Promise<void> => {
  await logIn(page)
  await expect(page.locator('.notice')).toContainText('Loaded')
}

const openRule = async (page: Page): Promise<void> => {
  await mockServer(page, false, RULES)
  await page.goto('/')
  await logInAndLoad(page)
  await page.locator('.rule-list li .select').first().click()
  await expect(page.locator('.rule-editor')).toBeVisible()
}

const inputValues = (page: Page) =>
  page
    .locator('.rule-editor input')
    .evaluateAll((items) => items.map((i) => (i as HTMLInputElement).value))

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

test('shows the mail as a chip that stops the filling', async ({ page }) => {
  await openRule(page)
  await expect(page.locator('.rule-editor .mail-chip')).toHaveCount(0)
  await openMail(page)
  await expect(page.locator('.rule-editor .mail-chip')).toContainText('Subject 3')
  await page.getByRole('button', { name: 'Do not fill from this mail' }).click()
  await expect(page.locator('.rule-editor .mail-chip')).toHaveCount(0)
  // The mail stays open in the panel, but the editor no longer fills from it.
  await expect(page.locator('.mail-panel .mail-message .subject')).toHaveText('Subject 3')
  await page.locator('.rule-editor .fill-from-mail').first().click()
  await expect.poll(() => inputValues(page)).not.toContain('Subject 3')
  await page.getByRole('button', { name: '‹ Messages' }).click()
  await page.locator('.mail-panel .row-mail').first().click()
  await expect(page.locator('.rule-editor .mail-chip')).toContainText('Subject 3')
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

test('an address condition starts filled and follows its part, but keeps a typed value', async ({
  page,
}) => {
  await openRule(page)
  await openMail(page)
  await page.getByLabel('Condition type').first().selectOption('address')
  await expect.poll(() => inputValues(page)).toContain('s3@example.com')
  await page.getByTitle('Which part of the address to compare').selectOption('name')
  await expect.poll(() => inputValues(page)).toContain('Sender 3')
  await page.getByTitle('Undo').click()
  await expect.poll(() => inputValues(page)).toContain('s3@example.com')
  await page.locator('.rule-editor .leaf input[placeholder="value"]').fill('typed')
  await page.getByTitle('Which part of the address to compare').selectOption('domain')
  await expect.poll(() => inputValues(page)).toContain('typed')
})

test('keeps the open mail after a reload', async ({ page }) => {
  await openRule(page)
  await openMail(page)
  await page.reload()
  await expect(page.locator('.notice')).toContainText('Loaded')
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

test('suggests the header names of the open mail on a header condition', async ({ page }) => {
  await mockServer(
    page,
    false,
    `rules:
  - name: Lists
    locations:
      - account_id: ${ACCOUNT_ID}
    when:
      type: header
      name: X-Header
      operator: contains
      value: ""
`,
  )
  await page.goto('/')
  await logInAndLoad(page)
  await page.locator('.rule-list li .select').first().click()
  await openMail(page)
  // The mail's own headers come first, then the common ones; none is repeated.
  const options = page.locator('.rule-editor datalist option')
  await expect(options.first()).toHaveAttribute('value', 'Subject')
  await expect(options.nth(1)).toHaveAttribute('value', 'List-Id')
  const values = await options.evaluateAll((items) => items.map((i) => i.getAttribute('value')))
  expect(new Set(values).size).toBe(values.length)
})
