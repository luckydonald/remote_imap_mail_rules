import { expect, test, type Page } from '@playwright/test'

/** Stands in for the token endpoints; a created token shows up in the list. */
const mockServer = async (page: Page): Promise<{ created: unknown[] }> => {
  const mock = { created: [] as unknown[] }
  const tokens: Record<string, unknown>[] = []
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/settings', (route) =>
    route.fulfill({
      json: {
        cache_unread: true,
        cache_opened_unread: true,
        cache_inbox: true,
        cache_inbox_count: 200,
        cache_max_age_days: 30,
      },
    }),
  )
  await page.route('**/api/mcp-tokens/scopes', (route) =>
    route.fulfill({
      json: {
        scopes: ['rules:read', 'rules:write', 'rules:delete', 'accounts.password:read'],
        presets: {
          read_only: ['rules:read'],
          everything: ['rules:read', 'rules:write', 'rules:delete'],
        },
      },
    }),
  )
  await page.route('**/api/mcp-tokens', async (route) => {
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData()!) as { name: string; scopes: string[] }
      mock.created.push(body)
      const row = {
        id: 'abc',
        name: body.name,
        prefix: 'rimr_xyz',
        scopes: body.scopes,
        created_at: '2026-11-12T10:00:00Z',
        last_used_at: null,
        revoked_at: null,
      }
      tokens.push(row)
      return route.fulfill({ status: 201, json: { ...row, token: 'rimr_xyzSECRETVALUE' } })
    }
    return route.fulfill({ json: tokens })
  })
  await page.route('**/api/mcp-tokens/abc', (route) => {
    tokens[0]!.revoked_at = '2026-11-12T11:00:00Z'
    return route.fulfill({ status: 204 })
  })
  return mock
}

test('creates a token with a preset, shows it once and revokes it', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/settings')
  await expect(page.getByText('No tokens yet.')).toBeVisible()
  await page.getByPlaceholder('Claude Code').fill('my client')
  await page.getByRole('button', { name: 'Read only' }).click()
  await page.getByRole('checkbox', { name: 'delete' }).check()
  await page.getByRole('button', { name: 'Create token' }).click()
  await expect(page.locator('.token-value')).toHaveText('rimr_xyzSECRETVALUE')
  expect(mock.created[0]).toEqual({ name: 'my client', scopes: ['rules:read', 'rules:delete'] })
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.token-value')).toHaveCount(0)
  await expect(page.getByText('rimr_xyz…')).toBeVisible()
  await page.getByRole('button', { name: 'Revoke', exact: true }).click()
  await page.getByRole('button', { name: 'Revoke for good' }).click()
  await expect(page.locator('.badge')).toHaveText('revoked')
})
