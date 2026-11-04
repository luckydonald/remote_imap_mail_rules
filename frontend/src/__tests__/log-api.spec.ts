import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/model/http'
import {
  fetchLog,
  fetchLogStatus,
  filtersOfQuery,
  logQuery,
  NO_FILTERS,
  queryOfFilters,
} from '@/model/log-api'

const json = (data: unknown, status = 200): Response =>
  new Response(JSON.stringify(data), { status })

afterEach(() => vi.unstubAllGlobals())

describe('log api', () => {
  it('sends only the filters that are set', () => {
    expect(logQuery(NO_FILTERS, null).toString()).toBe('limit=50')
    const query = logQuery(
      {
        ...NO_FILTERS,
        q: ' invoice ',
        account_id: 'a1',
        kinds: ['action', 'user_action'],
        since: '2026-11-03T10:00',
      },
      'cursor|1',
      20,
    )
    expect(query.get('q')).toBe('invoice')
    expect(query.get('account_id')).toBe('a1')
    expect(query.getAll('kind')).toEqual(['action', 'user_action'])
    expect(query.get('since')).toBe(new Date('2026-11-03T10:00').toISOString())
    expect(query.get('before')).toBe('cursor|1')
    expect(query.get('limit')).toBe('20')
    expect(query.has('until')).toBe(false)
  })

  it('ignores a time that does not parse', () => {
    expect(logQuery({ ...NO_FILTERS, until: 'soon' }, null).has('until')).toBe(false)
  })

  it('reads a page and the status', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(json({ items: [], next: null }))
      .mockResolvedValueOnce(json({ watcher_enabled: true, last_run: null }))
    vi.stubGlobal('fetch', fetchMock)
    expect((await fetchLog({ ...NO_FILTERS, folder: 'INBOX' }, null)).next).toBeNull()
    expect(fetchMock).toHaveBeenCalledWith('/api/log/events?limit=50&folder=INBOX')
    expect((await fetchLogStatus()).watcher_enabled).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/log/status')
  })

  it('fails with the status', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(json({ detail: 'no' }, 401)))
    await expect(fetchLogStatus()).rejects.toBeInstanceOf(ApiError)
    await expect(fetchLogStatus()).rejects.toMatchObject({ status: 401 })
  })
})

describe('log filters in the url', () => {
  it('round trips and drops what is empty or unknown', () => {
    expect(queryOfFilters(NO_FILTERS)).toEqual({})
    const filters = { ...NO_FILTERS, q: 'x', account_id: 'a1', kinds: ['action' as const] }
    expect(queryOfFilters(filters)).toEqual({ q: 'x', account: 'a1', kind: ['action'] })
    expect(filtersOfQuery(queryOfFilters(filters))).toEqual(filters)
    expect(filtersOfQuery({ kind: ['bogus', 'first_seen'] }).kinds).toEqual(['first_seen'])
    expect(filtersOfQuery({ kind: 'action' }).kinds).toEqual(['action'])
  })
})
