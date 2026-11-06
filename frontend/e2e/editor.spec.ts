import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const rulesDir = resolve(import.meta.dirname, '../../rules')
const EXAMPLES = ['example.yml', 'rules.example.yml']

const openFile = async (page: Page, name: string): Promise<void> => {
  await page.locator('input[type=file]').setInputFiles(resolve(rulesDir, name))
  await expect(page.locator('.notice')).toContainText(`Opened ${name}`)
}

test.beforeEach(async ({ page }) => {
  await page.goto('/')
})

for (const name of EXAMPLES) {
  test(`opens ${name} and shows it as valid`, async ({ page }) => {
    await openFile(page, name)
    await expect(page.locator('.topbar .source-menu summary')).toHaveText(`🕳️ In Memory · ${name}`)
    await expect(page.locator('.topbar .badge.ok')).toHaveText('valid')
    await expect(page.locator('.rule-list ul').first().locator('li .select').first()).toBeVisible()
  })
}

test('opens a file dropped onto the page', async ({ page }) => {
  const text = readFileSync(resolve(rulesDir, 'example.yml'), 'utf-8')
  const data = await page.evaluateHandle((content) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([content], 'dropped.yml', { type: 'text/yaml' }))
    return transfer
  }, text)
  await page.dispatchEvent('.app', 'dragover', { dataTransfer: data })
  await expect(page.locator('.drop')).toBeVisible()
  await page.dispatchEvent('.app', 'drop', { dataTransfer: data })
  await expect(page.locator('.topbar .source-menu summary')).toHaveText(
    '🕳️ In Memory · dropped.yml',
  )
  await expect(page.locator('.drop')).toBeHidden()
})

test('edits a rule, validates live, and undoes and redoes', async ({ page }) => {
  await openFile(page, 'example.yml')
  const name = page.getByLabel('Rule name')
  const original = await name.inputValue()

  await name.fill('Renamed rule')
  await expect(page.locator('.rule-list li.active .name')).toHaveText('Renamed rule')

  // An account id that is no UUID is a schema error.
  const account = page.getByPlaceholder('Account id (UUID, IMAP_ACCOUNT_ID)').first()
  await account.fill('nope')
  await expect(page.locator('.topbar .badge.error')).toContainText('problem')
  await expect(page.locator('.rule-editor .problems')).toBeVisible()

  const undo = page.getByTitle('Undo')
  const redo = page.getByTitle('Redo')
  await expect(undo).toBeEnabled()
  await undo.click()
  await expect(page.locator('.topbar .badge.ok')).toBeVisible()
  await expect(redo).toBeEnabled()
  await redo.click()
  await expect(page.locator('.topbar .badge.error')).toBeVisible()
  await undo.click()
  await undo.click()
  await expect(name).toHaveValue(original)
  // The history starts with the opened file, the document before it is kept in the source menu.
  await expect(undo).toBeDisabled()
})

test('adds, duplicates, moves and removes rules', async ({ page }) => {
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('button', { name: '+ New rule' }).click()
  await expect(page.locator('.rule-list ul').first().locator('li .select')).toHaveCount(1)
  await page.getByTitle('Duplicate').click()
  await expect(page.locator('.rule-list ul').first().locator('li .name').nth(1)).toHaveText(
    'New rule (copy)',
  )
  await page.getByTitle('Move up').click()
  await expect(page.locator('.rule-list ul').first().locator('li .name').first()).toHaveText(
    'New rule (copy)',
  )
  await page.getByTitle('Delete').click()
  await expect(page.locator('.rule-list ul').first().locator('li .select')).toHaveCount(1)
})

test('edits locations, actions and the condition tree', async ({ page }) => {
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('button', { name: '+ New rule' }).click()

  await page.getByRole('button', { name: '+ Add location' }).click()
  await expect(page.getByPlaceholder('Folder')).toHaveCount(2)
  await page.getByTitle('Remove location').first().click()
  await expect(page.getByPlaceholder('Folder')).toHaveCount(1)

  const action = page.locator('.model select').last()
  await page.getByRole('button', { name: /add action/i }).click()
  await action.selectOption('move')
  await page.getByPlaceholder('Target folder').fill('Archive/Old')

  await page.locator('.rule-list').getByText('YAML', { exact: true }).click()
  const yaml = page.getByLabel('YAML')
  await expect(yaml).toHaveValue(/type: move/)
  await expect(yaml).toHaveValue(/folder: Archive\/Old/)
})

test('edits templates', async ({ page }) => {
  await openFile(page, 'rules.example.yml')
  await page.locator('.rule-list').getByText('Templates').click()
  await expect(page.locator('main input').first()).toHaveValue('anonaddy-forward')
})

test('applies YAML typed into the YAML view', async ({ page }) => {
  const yaml = page.getByLabel('YAML')
  await yaml.fill(
    'rules:\n  - name: From text\n    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]\n    when: {type: bool, field: seen}\n',
  )
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('.rule-list ul').first().locator('li .name').first()).toHaveText(
    'From text',
  )
  await expect(page.locator('.topbar .badge.ok')).toBeVisible()
})

test('shows an error for broken YAML', async ({ page }) => {
  await page.getByLabel('YAML').fill('rules: [\n')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('.message.error')).toBeVisible()
})

test('downloads the YAML under the opened file name', async ({ page }) => {
  await openFile(page, 'rules.example.yml')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download' }).click(),
  ])
  expect(download.suggestedFilename()).toBe('rules.example.yml')
  const path = await download.path()
  const text = readFileSync(path, 'utf-8')
  expect(text).toContain('<<: *template-anonaddy-forward')
  expect(text).toContain('rules:')
})

test('keeps comments of the opened file in the download', async ({ page }) => {
  await openFile(page, 'rules.example.yml')
  await page.getByLabel('Rule name').fill('Renamed by the test')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download' }).click(),
  ])
  const text = readFileSync(await download.path(), 'utf-8')
  expect(text).toContain('name: Renamed by the test')
  expect(text).toContain('# A mail forwarded by anonaddy')
  expect(text).toContain('# Used when a rule does not set the variable.')
})

test('copies the YAML', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await openFile(page, 'example.yml')
  await page.getByRole('button', { name: 'Copy YAML' }).click()
  await expect(page.locator('.notice')).toHaveText('YAML copied.')
  const text = await page.evaluate(() => navigator.clipboard.readText())
  expect(text).toContain('rules:')
})

test.describe('cut and paste of rule blocks', () => {
  /** Two new rules, each with its `when` wrapped in an `all` group, with the first one's second condition made a `bool`. */
  const twoRules = async (page: Page): Promise<void> => {
    await page.getByRole('button', { name: 'New', exact: true }).click()
    for (let index = 0; index < 2; index++) {
      await page.getByRole('button', { name: '+ New rule' }).click()
      await page.getByTitle('Wrap in ALL (AND)').click()
    }
    await page.locator('.rule-list li .select').first().click()
    await page.getByRole('button', { name: '+ Add condition' }).click()
    await page.locator('.node-bar select').last().selectOption('bool')
  }

  test('moves a block into another rule through the real clipboard', async ({
    page,
    context,
  }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await twoRules(page)
    // `.cut` buttons: the group, then its two children.
    await page.locator('button.cut').last().click()
    await expect(page.locator('.node-bool')).toHaveCount(0)
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('type: bool')

    await page.locator('.rule-list li .select').nth(1).click()
    await page.getByRole('button', { name: 'Paste', exact: true }).click()
    await expect(page.locator('.node-bool')).toHaveCount(1)

    await page.locator('.rule-list').getByText('YAML', { exact: true }).click()
    await expect(page.getByLabel('YAML')).toHaveValue(/type: bool/)
  })

  test('keeps the clipboard untouched with the settings off, and still pastes the cut block', async ({
    page,
    context,
  }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.evaluate(() => navigator.clipboard.writeText('untouched'))
    await page.evaluate(() =>
      localStorage.setItem('mail-prefs', JSON.stringify({ copyCut: 'off', readPaste: 'off' })),
    )
    await page.reload()
    await twoRules(page)
    await page.locator('button.cut').last().click()
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('untouched')

    await page.locator('.rule-list li .select').nth(1).click()
    await page.getByRole('button', { name: 'Paste', exact: true }).click()
    await expect(page.locator('.node-bool')).toHaveCount(1)
  })
})

test.describe('color scheme', () => {
  const background = (page: Page) =>
    page.evaluate(() => getComputedStyle(document.body).backgroundColor)

  test('follows the system, light', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    const light = await background(page)
    await page.emulateMedia({ colorScheme: 'dark' })
    const dark = await background(page)
    expect(dark).not.toBe(light)
  })

  test('data-theme=light overrides a dark system', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    const light = await background(page)
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'))
    expect(await background(page)).toBe(light)
  })
})

test('asks before the page closes only while there are unsaved edits', async ({ page }) => {
  const prevented = (): Promise<boolean> =>
    page.evaluate(() => {
      const event = new Event('beforeunload', { cancelable: true })
      window.dispatchEvent(event)
      return event.defaultPrevented
    })
  expect(await prevented()).toBe(false)
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('button', { name: '+ New rule' }).click()
  expect(await prevented()).toBe(true)
})

test('asks before renaming a template variable in its uses', async ({ page }) => {
  await openFile(page, 'rules.example.yml')
  await page.locator('.rule-list').getByText('Templates').click()
  const variable = page.locator('.template .var-name').first()
  const old = await variable.inputValue()
  await variable.fill('renamed_var')
  const box = page.locator('.rename-box')
  await expect(box).toContainText(`${old} → renamed_var`)
  await box.getByText('No', { exact: true }).click()
  await expect(page.locator('.rename-chip')).toBeVisible()
  await page.locator('.rename-chip').click()
  await box.getByText('Yes', { exact: true }).click()
  await expect(page.locator('.rename')).toHaveCount(0)
  await page.locator('.rule-list').getByText('YAML', { exact: true }).click()
  await expect(page.getByLabel('YAML')).toHaveValue(/renamed_var/)
})
