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
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', file_name: 'server-rules.yml', exists: true } }),
  )
  await page.route('**/api/editor/rules', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') return route.fulfill({ body: RULES, contentType: 'text/plain' })
    mock.puts.push(request.postData() ?? '')
    if (rejectWith) return route.fulfill({ status: 422, json: { detail: rejectWith } })
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
  await expect(page.locator('.notice')).toContainText('Not saved: rules.0.locations: Field required')
})

test('stays file based without a server', async ({ page }) => {
  await page.route('**/api/editor/config', (route) => route.abort())
  await page.goto('/')
  await expect(page.getByRole('button', { name: /^Save/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Download' })).toBeVisible()
})
