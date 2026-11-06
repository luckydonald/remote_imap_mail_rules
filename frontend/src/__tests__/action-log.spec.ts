import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import ActionLogView from '@/components/ActionLogView.vue'
import type { LogEntry } from '@/model/log-api'
import { fullDate } from '@/model/mail-format'
import { createAppRouter } from '@/router'

const ACCOUNT = '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11'

const entry = (uid: number, kind: LogEntry['kind'], rule: string | null = null): LogEntry => ({
  id: `e${uid}${kind}`,
  account_id: ACCOUNT,
  folder: 'INBOX',
  uid,
  message_id: null,
  kind,
  rule_name: rule,
  detail: kind === 'rule_match' ? { match_kind: 'new' } : {},
  created_at: '2026-11-03T10:00:00Z',
})

const STATUS = {
  watcher_enabled: true,
  last_run: '2026-11-03T10:05:00Z',
  next_run: '2026-11-03T10:10:00Z',
  push: false,
  last_change: '2026-11-03T10:00:00Z',
  last_action: null,
  jobs: [],
}

const json = (data: unknown): Response => new Response(JSON.stringify(data))

/** Answers by path; `events` is called with the query of the request. */
function stubServer(events: (query: URLSearchParams) => unknown, status: unknown = STATUS) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/log/status') return json(status)
    if (url.pathname === '/api/log/events') return json(events(url.searchParams))
    if (url.pathname === '/api/accounts') return json([{ id: ACCOUNT, name: 'Work' }])
    return new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function mountView(path = '/log') {
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  const wrapper = mount(ActionLogView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }))
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('ActionLogView', () => {
  it('shows the status box and the entries with their mail', async () => {
    stubServer(() => ({
      items: [entry(1, 'rule_match', 'invoices'), entry(2, 'first_seen')],
      next: null,
    }))
    const { wrapper } = await mountView()
    expect(wrapper.get('[data-test=last-run]').text()).not.toBe('')
    expect(wrapper.get('[data-test=last-action]').text()).toBe('never')
    const rows = wrapper.findAll('.entries li')
    expect(rows.map((row) => row.get('.what').text())).toEqual([
      'Matched the rule "invoices" (new)',
      'First seen',
    ])
    expect(rows[0]!.get('.where').text()).toBe('Work · INBOX · 1')
    expect(rows[0]!.get('.where').attributes('href')).toBe(`/mail/${ACCOUNT}/INBOX/1`)
  })

  it('lists the working jobs and asks again for them', async () => {
    const running = {
      ...STATUS,
      jobs: [
        {
          kind: 'folder',
          account_id: ACCOUNT,
          folder: 'INBOX',
          uid: null,
          started_at: '2026-11-03T10:00:00Z',
        },
        {
          kind: 'actions',
          account_id: ACCOUNT,
          folder: 'INBOX',
          uid: 7,
          started_at: '2026-11-03T10:00:01Z',
        },
      ],
    }
    const fetchMock = stubServer(() => ({ items: [], next: null }), running)
    const { wrapper } = await mountView()
    const rows = wrapper.findAll('[data-test=jobs] li')
    expect(rows.map((row) => row.get('.what').text())).toEqual([
      'Checking folder',
      'Running rules on mail',
    ])
    expect(rows[0]!.find('a').exists()).toBe(false)
    expect(rows[1]!.get('a').attributes('href')).toBe(`/mail/${ACCOUNT}/INBOX/7`)
    expect(wrapper.find('[data-test=no-jobs]').exists()).toBe(false)

    const statusCalls = () =>
      fetchMock.mock.calls.filter(([url]) => String(url).includes('/status')).length
    const before = statusCalls()
    await vi.advanceTimersByTimeAsync(5100)
    expect(statusCalls()).toBe(before + 1)
  })

  it('says when nothing is running', async () => {
    stubServer(() => ({ items: [], next: null }))
    const { wrapper } = await mountView()
    expect(wrapper.get('[data-test=no-jobs]').text()).toBe('Nothing is running right now.')
  })

  it('says why there is no last run', async () => {
    stubServer(() => ({ items: [], next: null }), { ...STATUS, last_run: null })
    expect((await mountView()).wrapper.get('[data-test=last-run]').text()).toBe(
      'not since the server started',
    )
    stubServer(() => ({ items: [], next: null }), {
      ...STATUS,
      watcher_enabled: false,
      last_run: null,
    })
    expect((await mountView()).wrapper.get('[data-test=last-run]').text()).toBe(
      'The watcher is switched off',
    )
  })

  it('says when the next run is, or why there is none', async () => {
    const text = async (status: unknown) => {
      stubServer(() => ({ items: [], next: null }), status)
      return (await mountView()).wrapper.get('[data-test=next-run]').text()
    }
    const polling = await text(STATUS)
    expect(polling).toBe(fullDate(STATUS.next_run))
    expect(await text({ ...STATUS, push: true })).toBe(`${polling} (and on server push)`)
    expect(await text({ ...STATUS, next_run: null, push: true })).toBe('on change (server push)')
    expect(await text({ ...STATUS, next_run: null })).toBe('not scheduled yet')
    expect(await text({ ...STATUS, watcher_enabled: false, next_run: null })).toBe(
      'The watcher is switched off',
    )
  })

  it('reads the filters from the url and asks again when one changes', async () => {
    const fetchMock = stubServer(() => ({ items: [], next: null }))
    const { wrapper, router } = await mountView('/log?q=bill&kind=action')
    const first = fetchMock.mock.calls
      .map(([url]) => String(url))
      .find((url) => url.includes('/events'))!
    expect(first).toContain('q=bill')
    expect(first).toContain('kind=action')
    expect((wrapper.get('input[type=search]').element as HTMLInputElement).value).toBe('bill')

    await wrapper.get('input[aria-label=Folder]').setValue('Archive')
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    const last = String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1]![0])
    expect(last).toContain('folder=Archive')
    expect(router.currentRoute.value.query.folder).toBe('Archive')
    expect(wrapper.get('.hint').text()).toBe('Nothing matches these filters.')
  })

  it('loads more with the cursor and appends', async () => {
    const fetchMock = stubServer((query) =>
      query.get('before') === null
        ? { items: [entry(2, 'first_seen')], next: 'cursor|1' }
        : { items: [entry(1, 'first_seen')], next: null },
    )
    const { wrapper } = await mountView()
    await wrapper.get('.action-log > button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.entries li')).toHaveLength(2)
    expect(String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1]![0])).toContain(
      'before=cursor%7C1',
    )
    expect(wrapper.find('.action-log > button').exists()).toBe(false)
  })

  it('asks to log in again on a 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async () => new Response('{"detail":"no"}', { status: 401 })),
    )
    const { wrapper } = await mountView()
    expect(wrapper.emitted('unauthorized')).toBeTruthy()
  })
})
