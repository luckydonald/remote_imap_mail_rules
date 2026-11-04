import { expect, test, type Page } from '@playwright/test'

const RULES = `# my comment
rules:
  - name: Newsletters
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:
      type: text
      field: subject
      operator: contains
      value: news
    actions: []
`

interface Mock {
  puts: string[]
}

/** Stands in for the FastAPI server, so the e2e run needs only vite. */
const mockServer = async (page: Page, rejectWith?: string[]): Promise<Mock> => {
  const mock: Mock = { puts: [] }
  let current = RULES
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({
      json: { mode: 'server', source: 'file', file_name: 'server-rules.yml', exists: true },
    }),
  )
  await page.route('**/api/editor/rules', async (route) => {
    const request = route.request()
    if (request.method() === 'GET')
      return route.fulfill({ body: current, contentType: 'text/plain' })
    mock.puts.push(request.postData() ?? '')
    if (rejectWith) return route.fulfill({ status: 422, json: { detail: rejectWith } })
    current = request.postData() ?? ''
    return route.fulfill({ status: 204 })
  })
  return mock
}

test('loads the rules from the server, saves an edit and keeps the comment', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await expect(page.locator('.notice')).toContainText('Loaded server-rules.yml')
  const save = page.getByRole('button', { name: /^Save/ })
  await expect(save).toBeDisabled()
  await page.getByTitle('Duplicate').first().click()
  await expect(save).toBeEnabled()
  await save.click()
  await expect(page.locator('.notice')).toContainText('Saved server-rules.yml')
  await expect(save).toBeDisabled()
  expect(mock.puts).toHaveLength(1)
  expect(mock.puts[0]).toContain('# my comment')
  expect(mock.puts[0]).toContain('Newsletters (copy)')
})

test('shows what the server rejected', async ({ page }) => {
  await mockServer(page, ['rules.0.locations: Field required'])
  await page.goto('/')
  await page.getByTitle('Duplicate').first().click()
  await page.getByRole('button', { name: /^Save/ }).click()
  await expect(page.locator('.notice')).toContainText(
    'Not saved: rules.0.locations: Field required',
  )
})

test('stays file based without a server', async ({ page }) => {
  await page.route('**/api/editor/config', (route) => route.abort())
  await page.goto('/')
  await expect(page.getByRole('button', { name: /^Save/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Download' })).toBeVisible()
})

test('edits the description of a rule and saves it', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await page.getByLabel('Rule description').fill('# why\nsecond line')
  await page.getByRole('button', { name: /^Save/ }).click()
  await expect(page.locator('.notice')).toContainText('Saved server-rules.yml')
  expect(mock.puts[0]).toContain('description:')
  expect(mock.puts[0]).toContain('# why')
})

test('names what is edited in every view', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await expect(page.locator('.topbar .source-menu')).toHaveText('📄 server-rules.yml')
  await expect(page.getByRole('button', { name: /^Save to server-rules.yml/ })).toBeVisible()
})

test('a dropped file is edited in memory and never written to the server', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  const data = await page.evaluateHandle(() => {
    const transfer = new DataTransfer()
    transfer.items.add(new File(['rules: []\n'], 'dropped.yml', { type: 'text/yaml' }))
    return transfer
  })
  await page.dispatchEvent('.app', 'drop', { dataTransfer: data })
  await expect(page.locator('.topbar .source-menu summary')).toHaveText(
    '🕳️ In Memory · dropped.yml',
  )
  await expect(page.getByRole('button', { name: /^Save to/ })).toHaveCount(0)

  await page.locator('.source-menu summary').click()
  await page.getByRole('button', { name: '📄 server-rules.yml' }).click()
  await expect(page.locator('.topbar .source-menu summary')).toHaveText('📄 server-rules.yml')
  expect(mock.puts).toHaveLength(0)
})

test('edits the raw text of the server file and saves it as typed', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/')
  await page.locator('.rule-list').getByRole('button', { name: 'YAML' }).click()
  const yaml = page.getByLabel('YAML')
  await expect(yaml).toHaveValue(RULES)
  const typed = `# typed by hand\n${RULES}`
  await yaml.fill(typed)
  await page.getByRole('button', { name: 'Save to server-rules.yml' }).last().click()
  await expect(page.locator('.yaml-panel .message')).toContainText('Saved to server-rules.yml')
  expect(mock.puts).toEqual([typed])
})

test("shows the server's rejection of the raw text inline", async ({ page }) => {
  await mockServer(page, ['rules.0.locations: Field required'])
  await page.goto('/')
  await page.locator('.rule-list').getByRole('button', { name: 'YAML' }).click()
  await page.getByLabel('YAML').fill(`${RULES}\n# more`)
  await page.getByRole('button', { name: 'Save to server-rules.yml' }).last().click()
  await expect(page.locator('.yaml-panel .message.error')).toContainText(
    'Not saved: rules.0.locations: Field required',
  )
})

test('applying raw text keeps the server file and its Save', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await page.locator('.rule-list').getByRole('button', { name: 'YAML' }).click()
  await page.getByLabel('YAML').fill('rules: []\n')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('.topbar .source-menu')).toHaveText('📄 server-rules.yml')
  await expect(page.locator('.topbar .save')).toBeEnabled()
})
