import { expect, test } from '@playwright/test'
import { ACCOUNT_ID, logIn, mockServer } from './mail-mock'

test('asks for a login, then browses folders, pages and reads a message', async ({ page }) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  await logIn(page)
  expect(calls[0]).toContain('"username":"me@example.com"')
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await expect(page.locator('.mail-log li')).toHaveCount(2)
  await expect(page.locator('.mail-log li').first()).toContainText('First seen')
  await expect(page.locator('.mail-log li').nth(1)).toContainText(
    'Matched the rule "invoices" (new)',
  )
  await expect(page.frameLocator('iframe.body-frame').locator('b')).toHaveText('rich')
  await expect(page.locator('iframe.body-frame')).toHaveAttribute(
    'sandbox',
    /^((?!allow-scripts).)*$/,
  )
})

test('reloads the folder list and the message list', async ({ page }) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.row-mail')).toHaveCount(2)
  const count = (suffix: string): number => calls.filter((call) => call.startsWith(suffix)).length
  const folders = count('/folders')
  const lists = count('/messages')
  await page.getByRole('button', { name: 'Reload folders' }).click()
  await expect.poll(() => count('/folders')).toBe(folders + 1)
  await page.getByRole('button', { name: 'Reload messages' }).click()
  await expect.poll(() => count('/messages')).toBe(lists + 1)
  await expect(page.locator('.row-mail')).toHaveCount(2)
})

test('lists all headers of a message, collapsed at first', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  const headers = page.locator('.all-headers')
  await expect(headers.locator('summary')).toHaveText('All headers (2)')
  await expect(headers.locator('dd', { hasText: '<news.example.com>' })).toBeHidden()
  await headers.locator('summary').click()
  await expect(headers.locator('dt').nth(1)).toHaveText('List-Id')
  await expect(headers.locator('dd', { hasText: '<news.example.com>' })).toBeVisible()
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
    await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
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
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message .mail-spinner')).toContainText('Loading…')
  release()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page.locator('.mail-message .mail-spinner')).toHaveCount(0)
})

test('the screens have their own URLs and the back button returns to the previous one', async ({
  page,
}) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await expect(page).toHaveURL(/\/rules$/)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page.locator('.mail-folders .folder')).toHaveCount(2)
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await page.goBack()
  await expect(page).toHaveURL(/\/rules$/)
  await expect(page.locator('.mail-folders')).toHaveCount(0)
})

test('the mail browser keeps account, folder and message in the URL', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX/3`)
  await page.locator('.mail-folders .folder', { hasText: 'Sent' }).click()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/Sent`)
  // The back button walks the places in reverse.
  await page.goBack()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX/3`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('INBOX')
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await page.goBack()
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
  await expect(page.locator('.mail-message h2')).toHaveCount(0)
})

test('opens a mail from its URL', async ({ page }) => {
  await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.goto(`/mail/${ACCOUNT_ID}/Sent/3`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('Sent')
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/Sent/3`)
  // A URL with only the account falls back to the inbox.
  await page.goto(`/mail/${ACCOUNT_ID}`)
  await expect(page.locator('.mail-folders .folder.active')).toContainText('INBOX')
  await expect(page).toHaveURL(`/mail/${ACCOUNT_ID}/INBOX`)
})

const MOVE_RULES = `rules:
  - name: sent copy
    locations:
      - account_id: ${ACCOUNT_ID}
        folder: INBOX
    when:
      type: bool
      field: seen
    actions:
      - type: move
        folder: Sent
`

async function openThird(page: import('@playwright/test').Page): Promise<void> {
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
}

test('marks the open mail unread and read again', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.getByRole('button', { name: 'Mark read' }).click()
  await expect(page.getByRole('button', { name: 'Mark unread' })).toBeVisible()
  await expect(page.locator('.row-mail.active')).not.toHaveClass(/unread/)
  expect(calls).toContain('body {"add":["\\\\Seen"],"remove":[]}')
})

test('moves the mail to a destination of the rules', async ({ page }) => {
  const calls = await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await page.getByRole('menuitem', { name: 'Sent' }).click()
  expect(calls).toContain('body {"folder":"Sent"}')
  await expect(page.locator('.row-mail')).toHaveCount(1)
})

test('only one dropdown menu is open, and a click outside closes it', async ({ page }) => {
  await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await expect(page.locator('.menu-pop')).toHaveCount(1)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await expect(page.locator('.menu-pop')).toHaveCount(1)
  await expect(page.getByRole('menuitem', { name: 'New rule from this mail' })).toBeVisible()
  await page.locator('.mail-message').click({ position: { x: 5, y: 300 } })
  await expect(page.locator('.menu-pop')).toHaveCount(0)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.menu-pop')).toHaveCount(0)
})

test('moves the mail to a folder picked in the tree under More', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.getByRole('button', { name: 'Move ▾' }).click()
  await page.getByRole('menuitem', { name: 'More …' }).click()
  await page.getByRole('treeitem', { name: /Sent/ }).click()
  expect(calls).toContain('body {"folder":"Sent"}')
})

test('shows the text version and remembers the choice', async ({ page }) => {
  await mockServer(page)
  await openThird(page)
  await expect(page.locator('iframe.body-frame')).toBeVisible()
  await page.getByRole('radio', { name: 'Text' }).click()
  await expect(page.locator('pre.body-text')).toHaveText('plain text')
  await page.reload()
  await expect(page.getByRole('radio', { name: 'Text' })).toHaveAttribute('aria-checked', 'true')
})

test('lists the blocked images and loads them on request', async ({ page }) => {
  const calls = await mockServer(page)
  await openThird(page)
  await page.locator('.blocked-images summary').click()
  await expect(page.locator('.blocked-images a')).toHaveCount(2)
  await expect(page.locator('.blocked-images a').first()).toHaveText('https://t.example/a.gif')
  await page.getByRole('button', { name: 'Load remote images' }).click()
  await expect(page.locator('.blocked-images')).toHaveCount(0)
  expect(calls.some((call) => call.includes('remote_images=true'))).toBe(true)
})

test('the header and the body scroll as one', async ({ page }) => {
  await mockServer(page)
  await openThird(page)
  const frame = page.locator('iframe.body-frame')
  const sizes = await frame.evaluate((element: HTMLIFrameElement) => ({
    frame: element.clientHeight,
    content: element.contentDocument?.documentElement.scrollHeight ?? 0,
  }))
  // The page scrolls, not the frame: its content fits into it.
  expect(sizes.content).toBeLessThanOrEqual(sizes.frame)
})

test('the rule button starts a rule from the mail', async ({ page }) => {
  await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'New rule from this mail' }).click()
  await expect(page).toHaveURL(/\/rules\/1$/)
})

test('the rule button selects the mail as the example without a new rule', async ({ page }) => {
  await mockServer(page, false, MOVE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Select as example mail' }).click()
  await expect(page).toHaveURL(/\/rules\/0$/)
  await expect(page.locator('.rule-editor .mail-chip')).toContainText('Subject 3')
  // Remove the chip, go back to the mail and select it again.
  await page.getByRole('button', { name: 'Do not fill from this mail' }).click()
  await expect(page.locator('.rule-editor .mail-chip')).toHaveCount(0)
  await page.goBack()
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Select as example mail' }).click()
  await expect(page.locator('.rule-editor .mail-chip')).toContainText('Subject 3')
})

for (const width of [1366, 1280, 900, 700, 390]) {
  test(`the rule menu is fully visible and its dialog on top at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 1366 ? 1024 : 720 })
    await mockServer(page, false, MOVE_RULES)
    await openThird(page)
    await page.getByRole('button', { name: 'Rule ▾' }).click()
    // The mail column scrolls and clips what sticks out of it.
    const inside = await page.locator('.menu-pop').evaluate((pop) => {
      const box = pop.getBoundingClientRect()
      const column = pop.closest('.mail-message')?.getBoundingClientRect()
      const right = Math.min(window.innerWidth, column?.right ?? 0)
      return box.left >= (column?.left ?? 0) && box.right <= right
    })
    expect(inside).toBe(true)
    await page.getByRole('menuitem', { name: 'Add to existing rule …' }).click()
    await expect(page.getByRole('dialog', { name: 'Add to a rule' })).toBeVisible()
    // Safari on an iPad clips a fixed dialog to the scrolling pane around it, which desktop engines (and so this test) do not.
    // So check the cause instead: the dialog sits directly in the body and no ancestor of it clips.
    await expect(page.locator('body > .modal-backdrop')).toHaveCount(1)
    const clipped = await page.locator('.modal').evaluate((element) => {
      for (let node = element.parentElement; node !== null; node = node.parentElement) {
        const style = getComputedStyle(node)
        if (style.overflowX !== 'visible' || style.overflowY !== 'visible') return true
      }
      return false
    })
    expect(clipped).toBe(false)
    // Every corner and the middle, a pane painted over one side would still leave the centre visible.
    const topmost = await page.locator('.modal').evaluate((element) => {
      const box = element.getBoundingClientRect()
      const points = [
        [box.left + 4, box.top + 4],
        [box.right - 4, box.top + 4],
        [box.left + 4, box.bottom - 4],
        [box.right - 4, box.bottom - 4],
        [box.left + box.width / 2, box.top + box.height / 2],
      ] as const
      return points.every(([x, y]) => {
        const hit = document.elementFromPoint(x, y)
        return hit !== null && element.contains(hit)
      })
    })
    expect(topmost).toBe(true)
  })
}

const TEMPLATE_RULES = `templates:
  by-sender: &by-sender
    type: template
    defaults: {}
    content:
      type: address
      field: from
      part: address
      operator: equals
      value: !var sender
rules:
  - name: sent copy
    locations:
      - account_id: ${ACCOUNT_ID}
        folder: INBOX
    when:
      type: bool
      field: seen
`

test('adds a template use to an existing rule with the variable filled from the mail', async ({
  page,
}) => {
  await mockServer(page, false, TEMPLATE_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Add to existing rule …' }).click()
  await page.getByLabel('Kind of condition').selectOption('template')
  await expect(page.locator('.template-fill')).toContainText('sender = s3@example.com')
  await page.locator('.insert-point').last().click()
  await expect(page).toHaveURL(/\/rules\/0$/)
  await expect(page.locator('.rule-editor')).toContainText('by-sender')
})

const TWO_CONDITIONS = `rules:
  - name: two conditions
    locations:
      - account_id: ${ACCOUNT_ID}
        folder: INBOX
    when:
      type: all
      conditions:
        - type: bool
          field: seen
        - type: bool
          field: flagged
`

test('inserts the condition at the clicked place between two others', async ({ page }) => {
  await mockServer(page, false, TWO_CONDITIONS)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Add to existing rule …' }).click()
  await page.getByRole('combobox', { name: 'Field' }).selectOption('subject')
  await page
    .getByRole('button', { name: 'Insert into two conditions, whole rule, position 2' })
    .click()
  await expect(page).toHaveURL(/\/rules\/0$/)
  const fields = page.locator(
    '.rule-editor .node-all > .node-body > .leaf, .rule-editor .node-all .leaf',
  )
  await expect(fields).toHaveCount(3)
  const values = await page
    .locator('.rule-editor .leaf input[placeholder="value"]')
    .evaluateAll((items) => items.map((i) => (i as HTMLInputElement).value))
  expect(values).toContain('Subject 3')
})

const MANY_RULES = `rules:
${Array.from(
  { length: 12 },
  (_, i) => `  - name: rule ${i}
    locations:
      - account_id: ${ACCOUNT_ID}
        folder: INBOX
    when:
      type: all
      conditions:
        - type: bool
          field: seen
        - type: bool
          field: flagged
`,
).join('')}`

test('with many rules the picker stays below the controls and the dialog does not scroll sidewards', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await mockServer(page, false, MANY_RULES)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Add to existing rule …' }).click()
  const layout = await page.locator('.modal').evaluate((element) => {
    const picker = element.querySelector('.insert-picker')?.getBoundingClientRect()
    const controls = [...element.querySelectorAll('label')].map((l) => l.getBoundingClientRect())
    return {
      // Once the content is taller than the dialog, a wrapping column puts the picker in a second column.
      below: controls.every((box) => (picker?.top ?? 0) >= box.bottom),
      sideways: element.scrollWidth > element.clientWidth,
    }
  })
  expect(layout).toEqual({ below: true, sideways: false })
})

test('the picker is a full-screen overlay with a back button on a phone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 720 })
  await mockServer(page, false, TWO_CONDITIONS)
  await openThird(page)
  await page.getByRole('button', { name: 'Rule ▾' }).click()
  await page.getByRole('menuitem', { name: 'Add to existing rule …' }).click()
  const box = await page.locator('.modal').boundingBox()
  expect(box?.width).toBe(390)
  expect(box?.height).toBe(720)
  await page.getByRole('button', { name: '‹ Back' }).click()
  await expect(page.getByRole('dialog', { name: 'Add to a rule' })).toHaveCount(0)
})

test('works offline from the cache and sends queued changes when the server is back', async ({
  page,
}) => {
  const calls = await mockServer(page)
  await page.goto('/')
  await logIn(page)
  await page.getByRole('link', { name: 'Mail', exact: true }).click()
  await page.locator('.row-mail', { hasText: 'Subject 3' }).click()
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  // Let the write-through to IndexedDB finish.
  await page.waitForTimeout(300)

  // The network is gone (a later route wins over the mocks).
  await page.route('**/api/**', (route) => route.abort('failed'))
  await page.reload()
  await expect(page.locator('.offline-banner')).toContainText('Offline')
  await expect(page.locator('.row-mail')).toHaveCount(2)
  await expect(page.locator('.mail-message h2')).toHaveText('Subject 3')
  await expect(page.locator('.mail-log-offline')).toContainText('Offline')
  await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible()

  await page.getByRole('button', { name: 'Mark read' }).click()
  await expect(page.getByRole('button', { name: 'Mark unread' })).toBeVisible()
  await expect(page.locator('.queue-count')).toHaveText('1')
  await page.locator('.queue-count').click()
  await expect(page.locator('.queue-row')).toHaveCount(1)
  await page.getByRole('button', { name: 'Close' }).click()

  // Logging out with unsent changes asks first.
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('dialog', { name: 'Unsent changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancel' }).click()

  await page.unroute('**/api/**')
  calls.length = 0
  await page.reload()
  await expect.poll(() => calls.some((call) => call.includes('/flags'))).toBe(true)
  await expect(page.locator('.queue-count')).toHaveCount(0)
})
