import { expect, test, type Page } from '@playwright/test'

const RULES = `rules:
  - name: Invoices
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:
      type: text
      field: subject
      operator: contains
      value: invoice
    actions:
      - type: mark_read
      - type: move
        folder: Archive
`

const ACCOUNT = '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11'

const mail = (uid: number, subject: string) => ({
  uid,
  account_id: ACCOUNT,
  folder: 'INBOX',
  subject,
  sender: { name: `Sender ${uid}`, address: `s${uid}@example.com` },
  date: '2026-10-01T08:30:00Z',
  rounds: [
    {
      rule: 'Invoices',
      steps: [
        { type: 'mark_read', status: 'planned', reason: null, args: {} },
        { type: 'move', status: 'planned', reason: null, args: { folder: 'Archive' } },
      ],
    },
  ],
  moved_to: 'Archive',
})

const RESULT = {
  rule: 'Invoices',
  actions_enabled: false,
  inspected: 40,
  affected: 2,
  summary: [
    { type: 'mark_read', status: 'planned', count: 2, folder: null, keyword: null, reason: null },
    { type: 'move', status: 'planned', count: 2, folder: 'Archive', keyword: null, reason: null },
  ],
  mails: [mail(1, 'invoice March'), mail(2, 'invoice April')],
  errors: [],
  next: null,
}

interface Mock {
  dryRuns: string[]
  runs: string[]
}

const mockServer = async (page: Page, actionsEnabled: boolean): Promise<Mock> => {
  const mock: Mock = { dryRuns: [], runs: [] }
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({
      json: { mode: 'server', source: 'file', file_name: 'rules.yml', exists: true, actions_enabled: actionsEnabled },
    }),
  )
  await page.route('**/api/editor/rules', (route) =>
    route.fulfill({ body: RULES, contentType: 'text/plain' }),
  )
  await page.route('**/api/mail/accounts**', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/accounts', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/dry-run', (route) => {
    mock.dryRuns.push(route.request().postData() ?? '')
    return route.fulfill({ json: { ...RESULT, actions_enabled: actionsEnabled } })
  })
  await page.route('**/api/dry-run/run', (route) => {
    mock.runs.push(route.request().postData() ?? '')
    return route.fulfill({ json: { applied: 2, steps: { done: 4 }, errors: [] } })
  })
  return mock
}

test('shows the summary and drills down into the mails', async ({ page }) => {
  const mock = await mockServer(page, false)
  await page.goto('/rules/0')
  await page.getByRole('button', { name: 'Dry run', exact: true }).click()
  await expect(page.locator('.totals')).toContainText('Looked at 40 mails, 2 would be affected')
  await expect(page.locator('.summary tr')).toHaveCount(2)
  await expect(page.locator('.summary')).toContainText('2×move to Archive')
  await expect(page.locator('.affected > li')).toHaveCount(2)
  await expect(page.locator('.chain').first()).toContainText('Invoices: mark as read, move to Archive')
  await page.locator('.summary tr', { hasText: 'mark as read' }).click()
  await expect(page.locator('.dry-run .hint', { hasText: 'Showing' })).toContainText('Showing 2 mails')
  expect(mock.dryRuns).toHaveLength(1)
  expect(mock.dryRuns[0]).toContain('"rule":"Invoices"')
  expect(mock.dryRuns[0]).toContain('Invoices')
})

test('Run now is disabled with a hint while the server does not apply rules', async ({ page }) => {
  const mock = await mockServer(page, false)
  await page.goto('/rules/0')
  await page.getByRole('button', { name: 'Dry run', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Run now' })).toBeDisabled()
  await expect(page.locator('.blocked')).toContainText('currently not applying rules')
  expect(mock.runs).toHaveLength(0)
})

test('Run now asks for confirmation and applies the rule', async ({ page }) => {
  const mock = await mockServer(page, true)
  await page.goto('/rules/0')
  await page.getByRole('button', { name: 'Dry run', exact: true }).click()
  await page.getByRole('button', { name: 'Run now' }).click()
  await expect(page.locator('.confirm')).toContainText('Apply 4 changes to 2 mails')
  expect(mock.runs).toHaveLength(0)
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('.notice-run')).toContainText('Applied to 2 mails (4 done)')
  expect(mock.runs).toEqual(['{"rule":"Invoices"}'])
})

test('loads the dry run in pages, skipping pages without mails', async ({ page }) => {
  const cursor = (before: number) => ({ account_id: ACCOUNT, folder: 'INBOX', before_uid: before })
  const one = RESULT.summary.map((row) => ({ ...row, count: 1 }))
  const pages = [
    { ...RESULT, inspected: 200, affected: 0, summary: [], mails: [], next: cursor(300) },
    { ...RESULT, inspected: 200, affected: 1, summary: one, mails: [mail(1, 'invoice March')], next: cursor(100) },
    { ...RESULT, inspected: 50, affected: 1, summary: one, mails: [mail(2, 'invoice April')], next: null },
  ]
  const bodies: string[] = []
  await mockServer(page, false)
  await page.route('**/api/dry-run', (route) => {
    bodies.push(route.request().postData() ?? '')
    return route.fulfill({ json: pages[bodies.length - 1] })
  })
  await page.goto('/rules/0')
  await page.getByRole('button', { name: 'Dry run', exact: true }).click()
  // The first page has no mail, so the second one comes without a click.
  await expect(page.locator('.affected > li')).toHaveCount(1)
  expect(bodies).toHaveLength(2)
  expect(bodies[0]).not.toContain('cursor')
  expect(bodies[1]).toContain('"before_uid":300')
  await expect(page.locator('.totals')).toContainText('Looked at 400 mails so far')
  await page.getByRole('button', { name: 'Load more…' }).click()
  await expect(page.locator('.affected > li')).toHaveCount(2)
  expect(bodies[2]).toContain('"before_uid":100')
  await expect(page.getByRole('button', { name: 'Load more…' })).toHaveCount(0)
  await expect(page.locator('.totals')).toContainText('Looked at 450 mails, 2 would be affected')
  await expect(page.locator('.summary')).toContainText('2×move to Archive')
})
