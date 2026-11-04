import type { Page } from '@playwright/test'

export const ACCOUNT_ID = '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11'

export const FOLDERS = [
  {
    name: 'INBOX',
    display_name: 'INBOX',
    delimiter: '/',
    special_use: 'inbox',
    selectable: true,
    messages: 3,
    unseen: 2,
  },
  {
    name: 'Sent',
    display_name: 'Sent',
    delimiter: '/',
    special_use: 'sent',
    selectable: true,
    messages: 1,
    unseen: 0,
  },
]

export const summary = (uid: number, seen = false) => ({
  uid,
  sender: { name: `Sender ${uid}`, address: `s${uid}@example.com` },
  subject: `Subject ${uid}`,
  date: '2026-10-01T08:30:00Z',
  seen,
  flagged: false,
  answered: false,
  has_attachments: uid === 3,
  size: 100,
})

export const DETAIL = {
  ...summary(3),
  to: [{ name: 'Me', address: 'me@example.com' }],
  cc: [],
  bcc: [],
  reply_to: [],
  sender_header: [],
  return_path: [],
  delivered_to: [],
  headers: [
    { name: 'Subject', value: 'Subject 3' },
    { name: 'List-Id', value: '<news.example.com>' },
  ],
  flags: ['\\Seen'],
  keywords: [],
  date_sent: '2026-10-01T08:00:00Z',
  mime_type: 'multipart/mixed',
  modseq: 9,
  message_id: '<m@x>',
  text: 'plain text',
  html: '<p>Hello <b>rich</b> world</p>',
  blocked_images: ['https://t.example/a.gif', 'https://t.example/b.gif'],
  broken_embeds: [],
  styles_blocked: false,
  remote_images_allowed: false,
  styles_allowed: false,
  attachments: [
    {
      part: '2',
      filename: 'report.pdf',
      mime_type: 'application/pdf',
      size: 2048,
      inline: false,
      content_id: null,
      extension: 'pdf',
      url: `/api/mail/accounts/${ACCOUNT_ID}/messages/3/parts/2?folder=INBOX`,
    },
  ],
}

/** The server: needs a login first, then serves one account with an inbox of three mails in two pages. */
export const mockServer = async (
  page: Page,
  wrongPassword = false,
  rulesYaml: string | null = null,
): Promise<string[]> => {
  const calls: string[] = []
  let loggedIn = false
  await page.route('**/api/editor/config', (route) =>
    loggedIn
      ? route.fulfill({
          json: {
            mode: 'server',
            source: 'database',
            file_name: null,
            exists: false,
            actions_enabled: true,
          },
        })
      : route.fulfill({ status: 401, json: { detail: 'Not logged in.' } }),
  )
  await page.route('**/api/editor/rules', (route) =>
    rulesYaml === null
      ? route.fulfill({ status: 404, json: {} })
      : route.fulfill({ contentType: 'text/plain', body: rulesYaml }),
  )
  await page.route('**/api/auth/login', (route) => {
    calls.push(`login ${route.request().postData()}`)
    if (wrongPassword)
      return route.fulfill({ status: 401, json: { detail: 'Wrong username or password.' } })
    loggedIn = true
    return route.fulfill({ status: 204 })
  })
  await page.route('**/api/auth/logout', (route) => {
    calls.push('logout')
    loggedIn = false
    return route.fulfill({ status: 204 })
  })
  await page.route('**/api/accounts', (route) =>
    route.fulfill({
      json: [
        {
          id: ACCOUNT_ID,
          name: 'Private',
          host: 'imap.example.com',
          port: 993,
          ssl: true,
          username: 'me@example.com',
          page_size: 50,
          poll_interval: 60,
          has_password: true,
          env_differs: [],
        },
      ],
    }),
  )
  await page.route('**/api/mail/**', (route) => {
    const url = new URL(route.request().url())
    calls.push(url.pathname.replace(`/api/mail/accounts/${ACCOUNT_ID}`, '') + url.search)
    if (url.pathname.endsWith('/folders')) return route.fulfill({ json: FOLDERS })
    if (url.pathname.endsWith('/events')) return route.fulfill({ json: EVENTS })
    if (url.pathname.endsWith('/messages') && url.searchParams.has('before_uid'))
      return route.fulfill({
        json: { messages: [summary(1, true)], total: 3, next_before_uid: null },
      })
    if (url.pathname.endsWith('/messages'))
      return route.fulfill({
        json: { messages: [summary(3), summary(2, true)], total: 3, next_before_uid: 2 },
      })
    if (url.pathname.endsWith('/flags') || url.pathname.endsWith('/move')) {
      calls.push(`body ${route.request().postData()}`)
      return url.pathname.endsWith('/move')
        ? route.fulfill({ json: { folder: 'Sent', uid: 1 } })
        : route.fulfill({ status: 204 })
    }
    if (url.searchParams.get('remote_images') === 'true')
      return route.fulfill({
        json: { ...DETAIL, blocked_images: [], remote_images_allowed: true },
      })
    return route.fulfill({ json: DETAIL })
  })
  return calls
}

export const EVENTS = [
  { id: 'e1', kind: 'first_seen', rule_name: null, detail: {}, created_at: '2026-11-03T10:00:00Z' },
  {
    id: 'e2',
    kind: 'rule_match',
    rule_name: 'invoices',
    detail: { match_kind: 'new' },
    created_at: '2026-11-03T10:00:05Z',
  },
]

export const logIn = async (page: Page): Promise<void> => {
  await page.getByLabel('Username').fill('me@example.com')
  await page.getByLabel('Password').fill('secret')
  await page.getByRole('button', { name: 'Log in' }).click()
}
