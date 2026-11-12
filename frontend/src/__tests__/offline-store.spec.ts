import 'fake-indexeddb/auto'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ConfirmLogout from '@/components/ConfirmLogout.vue'
import MailLog from '@/components/MailLog.vue'
import OfflineBanner from '@/components/OfflineBanner.vue'
import OnlineOnly from '@/components/OnlineOnly.vue'
import { clearAll } from '@/model/offline/db'
import { queued } from '@/model/offline/queue'
import { setOnline } from '@/model/online'
import { useStore } from '@/model/store'

const summary = (uid: number) => ({
  uid,
  sender: { name: 'Max', address: 'max@example.com' },
  subject: `mail ${uid}`,
  date: null,
  seen: false,
  flagged: false,
  answered: false,
  has_attachments: false,
  size: 10,
  uidvalidity: 1,
})
const detail = (uid: number) => ({
  ...summary(uid),
  to: [],
  cc: [],
  bcc: [],
  reply_to: [],
  sender_header: [],
  return_path: [],
  delivered_to: [],
  headers: [],
  flags: [],
  keywords: [],
  date_sent: null,
  mime_type: null,
  modseq: null,
  message_id: null,
  text: `body ${uid}`,
  html: null,
  attachments: [],
})

let down = false
const calls: string[] = []

function stubServer(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>().mockImplementation((input, init) => {
      const url = String(input)
      if (down) return Promise.reject(new TypeError('Failed to fetch'))
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      const json = (body: unknown): Promise<Response> =>
        Promise.resolve(new Response(JSON.stringify(body)))
      if (url === '/api/accounts') return json([{ id: 'acc', name: 'Private' }])
      if (url.endsWith('/folders'))
        return json([
          {
            name: 'INBOX',
            display_name: 'INBOX',
            delimiter: '/',
            special_use: 'inbox',
            selectable: true,
            messages: 2,
            unseen: 2,
          },
        ])
      if (url.includes('/events?')) return json([])
      if (url.includes('/move?')) return json({ folder: 'Archive', uid: 50 })
      if (url.includes('/flags?')) return Promise.resolve(new Response(null, { status: 204 }))
      if (url.includes('/messages?'))
        return json({
          messages: [summary(2), summary(1)],
          total: 2,
          next_before_uid: null,
          uidvalidity: 1,
        })
      return json(detail(Number(url.match(/messages\/(\d+)/)?.[1] ?? 1)))
    }),
  )
}

beforeEach(async () => {
  setActivePinia(createPinia())
  localStorage.clear()
  await clearAll()
  queued.value = []
  down = false
  calls.length = 0
  setOnline(true)
  stubServer()
})
afterEach(() => vi.unstubAllGlobals())

describe('reading offline', () => {
  it('shows the cached folders, list and mail when the network is gone', async () => {
    const first = useStore()
    await first.loadAccounts()
    await first.openMessage(2)
    down = true
    setActivePinia(createPinia())
    const store = useStore()
    await store.loadAccounts()
    expect(store.isOnline).toBe(false)
    expect(store.folders.map((f) => f.name)).toEqual(['INBOX'])
    expect(store.messages.map((m) => m.uid)).toEqual([2, 1])
    await store.openMessage(2)
    expect(store.detail?.text).toBe('body 2')
    expect(store.eventsOffline).toBe(true)
    expect(store.error).toBe('')
  })

  it('shows an error for a mail that was never cached', async () => {
    const first = useStore()
    await first.loadAccounts()
    down = true
    await first.openMessage(2)
    expect(first.detail).toBeNull()
    expect(first.error).toContain('Could not load the message')
  })
})

describe('actions offline', () => {
  it('queues mark read, applies it locally and sends it when the server is back', async () => {
    const store = useStore()
    await store.loadAccounts()
    await store.openMessage(2)
    down = true
    await store.setSeen(true)
    expect(store.error).toBe('')
    expect(store.detail?.seen).toBe(true)
    expect(store.queued).toHaveLength(1)
    expect(store.isOnline).toBe(false)
    down = false
    await store.sendQueue()
    expect(store.queued).toHaveLength(0)
    expect(calls.some((c) => c.startsWith('POST') && c.includes('/messages/2/flags?'))).toBe(true)
  })

  it('queues a move, takes the mail out of the list and sends it later', async () => {
    const store = useStore()
    await store.loadAccounts()
    await store.openMessage(2)
    down = true
    await store.moveTo('Archive')
    expect(store.messages.map((m) => m.uid)).toEqual([1])
    expect(store.queued.map((e) => e.kind)).toEqual(['move'])
    down = false
    await store.sendQueue()
    expect(store.queued).toHaveLength(0)
    expect(calls.some((c) => c.includes('/messages/2/move?'))).toBe(true)
  })

  it('a rejection by the server is still an error, not a queue entry', async () => {
    const store = useStore()
    await store.loadAccounts()
    await store.openMessage(2)
    ;(fetch as ReturnType<typeof vi.fn>).mockImplementationOnce(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: 'actions_disabled' }), { status: 409 }),
      ),
    )
    await store.setSeen(true)
    expect(store.queued).toHaveLength(0)
    expect(store.error).toContain('actions_disabled')
  })
})

describe('offline widgets', () => {
  it('the banner shows the count and its click opens the list of queued actions', async () => {
    const store = useStore()
    await store.loadAccounts()
    await store.openMessage(2)
    down = true
    await store.setSeen(true)
    store.active = true
    const wrapper = mount(OfflineBanner, { attachTo: document.body })
    expect(wrapper.text()).toContain('Offline')
    await wrapper.find('button.queue-count').trigger('click')
    const rows = document.body.querySelectorAll('.queue-row')
    expect(rows).toHaveLength(1)
    expect(rows[0]!.textContent).toContain('flag')
    expect(rows[0]!.textContent).toContain('INBOX')
    wrapper.unmount()
  })

  it('OnlineOnly disables what is inside while offline', async () => {
    const wrapper = mount(OnlineOnly, { slots: { default: '<button>Save</button>' } })
    expect(wrapper.find('button').element.matches(':disabled')).toBe(false)
    setOnline(false)
    await flushPromises()
    expect(wrapper.find('button').element.matches(':disabled')).toBe(true)
    expect(wrapper.find('fieldset').attributes('title')).toBe('Not available offline')
  })

  it('the mail log says it is offline instead of showing nothing', () => {
    const wrapper = mount(MailLog, { props: { events: [], offline: true } })
    expect(wrapper.text()).toContain('Offline')
  })

  it('the logout dialog offers send, log out anyway and cancel', async () => {
    const wrapper = mount(ConfirmLogout, { props: { count: 2 }, attachTo: document.body })
    expect(document.body.textContent).toContain('2 changes have not been sent')
    const buttons = [...document.body.querySelectorAll('footer button')] as HTMLButtonElement[]
    buttons.forEach((b) => b.click())
    expect(Object.keys(wrapper.emitted())).toEqual(
      expect.arrayContaining(['cancel', 'logout', 'send']),
    )
    wrapper.unmount()
  })
})
