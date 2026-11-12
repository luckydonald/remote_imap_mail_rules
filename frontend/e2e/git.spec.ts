import { expect, test, type Page } from '@playwright/test'

const SETTINGS = {
  enabled: true,
  auto_commit: false,
  auto_push: false,
  remote_url: '',
  branch: 'main',
  auth_method: 'none',
  username: '',
  has_token: false,
  author_name: 'Tester',
  author_email: 'tester@example.com',
}

const STATUS: Record<string, unknown> = {
  git_available: true,
  initialized: false,
  branch: null,
  changed: [],
  has_upstream: false,
  ahead: 0,
  behind: 0,
  last_commit: null,
  remote_configured: false,
}

/** Stands in for the git endpoints; the state follows what is clicked. */
const mockServer = async (page: Page): Promise<{ saved: unknown[] }> => {
  const mock = { saved: [] as unknown[] }
  let settings = { ...SETTINGS }
  let status = { ...STATUS }
  const state = () => ({
    settings,
    status,
    public_key: null,
    last_error: null,
    directory: '/data/rules',
  })
  await page.route('**/api/editor/config', (route) =>
    route.fulfill({ json: { mode: 'server', source: 'database', file_name: null, exists: false } }),
  )
  await page.route('**/api/editor/rules', (route) => route.fulfill({ status: 404, json: {} }))
  await page.route('**/api/git/**', async (route) => {
    const url = new URL(route.request().url())
    const action = url.pathname.split('/').pop()
    if (action === 'settings') {
      const body = JSON.parse(route.request().postData()!)
      mock.saved.push(body)
      const { token: _token, ...rest } = body
      settings = { ...settings, ...rest }
      return route.fulfill({ json: state() })
    }
    if (action === 'init')
      status = { ...status, initialized: true, branch: 'main', changed: ['rules.yml'] }
    if (action === 'commit')
      status = {
        ...status,
        changed: [],
        last_commit: 'abc1234 Update rules (now)',
        ahead: 1,
        remote_configured: true,
      }
    if (action === 'push') status = { ...status, ahead: 0, has_upstream: true }
    if (action === 'ssh-key')
      return route.fulfill({ json: { ...state(), public_key: 'ssh-ed25519 AAAA test' } })
    return route.fulfill({ json: { done: true, state: state() } })
  })
  await page.route('**/api/git', (route) => route.fulfill({ json: state() }))
  return mock
}

test('shows the state and walks init, commit and push', async ({ page }) => {
  await mockServer(page)
  await page.goto('/settings/git')
  await expect(page.locator('.badge.error').first()).toContainText('not initialised')
  await expect(page.getByRole('button', { name: 'Commit now' })).toBeDisabled()
  await page.getByRole('button', { name: 'Initialise' }).click()
  await expect(page.locator('.status')).toContainText('1 uncommitted')
  await page.getByRole('button', { name: 'Commit now' }).click()
  await expect(page.locator('.status')).toContainText('clean')
  await expect(page.locator('.status')).toContainText('1 to push')
  // Pushing needs a remote URL.
  await expect(page.getByRole('button', { name: 'Push now' })).toBeDisabled()
})

test('saves the check boxes, and automatic push needs automatic commit', async ({ page }) => {
  const mock = await mockServer(page)
  await page.goto('/settings/git')
  const autoPush = page.locator('input[name=auto_push]')
  await expect(autoPush).toBeDisabled()
  await page.locator('input[name=auto_commit]').check()
  await expect(autoPush).toBeEnabled()
  await autoPush.check()
  await page.locator('input[name=remote_url]').fill('https://example.com/r.git')
  await page.locator('.git-form').getByRole('button', { name: 'Save' }).click()
  await expect(page.locator('.message')).toContainText('Saved.')
  expect(mock.saved[0]).toMatchObject({ auto_commit: true, auto_push: true, token: null })
  await page.locator('input[name=auto_commit]').uncheck()
  await expect(autoPush).not.toBeChecked()
})

test('generates and shows the SSH key', async ({ page }) => {
  await mockServer(page)
  await page.goto('/settings/git')
  await page.locator('select[name=auth_method]').selectOption('ssh')
  await page.getByRole('button', { name: 'Generate key' }).click()
  await expect(page.locator('.key')).toContainText('ssh-ed25519 AAAA')
})
