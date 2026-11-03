import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMailStore } from '@/model/mail-store'
import { folderLabel, shortDate } from '@/model/mail-format'
import type { Folder, Summary } from '@/model/mail-api'

const ACCOUNT = { id: 'acc', name: 'Private' }
const folder = (name: string, extra: Partial<Folder> = {}): Folder => ({
  name,
  display_name: name,
  delimiter: '/',
  special_use: null,
  selectable: true,
  messages: 3,
  unseen: 1,
  ...extra,
})
const mail = (uid: number): Summary => ({
  uid,
  sender: { name: 'Max', address: 'max@example.com' },
  subject: `mail ${uid}`,
  date: null,
  seen: false,
  flagged: false,
  answered: false,
  has_attachments: false,
  size: 10,
})

/** Routes by URL, so the order of the store's requests does not matter. */
function stubServer(unauthorized = false): ReturnType<typeof vi.fn<typeof fetch>> {
  const fetchMock = vi.fn<typeof fetch>().mockImplementation((input) => {
    const url = String(input)
    const json = (body: unknown, status = 200): Promise<Response> =>
      Promise.resolve(new Response(JSON.stringify(body), { status }))
    if (unauthorized) return json({ detail: 'Not logged in.' }, 401)
    if (url === '/api/accounts') return json([ACCOUNT])
    if (url.endsWith('/folders'))
      return json([
        folder('INBOX', { special_use: 'inbox' }),
        folder('Hidden', { selectable: false }),
      ])
    if (url.includes('before_uid='))
      return json({ messages: [mail(1)], total: 3, next_before_uid: null })
    if (url.includes('/messages?'))
      return json({ messages: [mail(3), mail(2)], total: 3, next_before_uid: 2 })
    return json({
      ...mail(3),
      to: [],
      cc: [],
      reply_to: [],
      message_id: null,
      text: 'hi',
      html: null,
      attachments: [],
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('mail store', () => {
  it('opens the inbox of the first account, pages and opens a message', async () => {
    stubServer()
    const store = createMailStore()
    await store.loadAccounts()
    expect(store.folder.value).toBe('INBOX')
    expect(store.folders.value.map((item) => item.name)).toEqual(['INBOX'])
    expect(store.messages.value.map((item) => item.uid)).toEqual([3, 2])
    expect(store.hasMore.value).toBe(true)
    expect(store.pane.value).toBe('list')
    await store.loadMore()
    expect(store.messages.value.map((item) => item.uid)).toEqual([3, 2, 1])
    expect(store.hasMore.value).toBe(false)
    await store.openMessage(3)
    expect(store.detail.value?.text).toBe('hi')
    expect(store.pane.value).toBe('message')
    store.back()
    expect(store.pane.value).toBe('list')
    store.back()
    expect(store.pane.value).toBe('folders')
  })

  it('asks to log in again on a 401', async () => {
    stubServer(true)
    const onUnauthorized = vi.fn<() => void>()
    const store = createMailStore(onUnauthorized)
    await store.loadAccounts()
    expect(onUnauthorized).toHaveBeenCalledOnce()
    expect(store.error.value).toBe('')
  })

  it('reports other errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(new Response('{"detail":"down"}', { status: 502 })),
    )
    const store = createMailStore()
    await store.loadAccounts()
    expect(store.error.value).toContain('down')
  })
})

describe('mail format', () => {
  it('indents sub folders and shows today as a time', () => {
    expect(folderLabel(folder('INBOX/Lists/a'))).toEqual({ name: 'a', depth: 2 })
    const now = new Date('2026-11-03T12:00:00')
    expect(shortDate('2026-11-03T08:30:00', now)).toMatch(/\d{1,2}:\d{2}/)
    expect(shortDate('2026-10-01T08:30:00', now)).toMatch(/2026/)
    expect(shortDate(null)).toBe('')
  })
})
