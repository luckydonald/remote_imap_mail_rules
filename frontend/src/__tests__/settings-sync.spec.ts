import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { usePrefs } from '@/model/store/prefs'

const SERVER = {
  cache_unread: false,
  cache_opened_unread: true,
  cache_inbox: true,
  cache_inbox_count: 50,
  cache_max_age_days: 7,
}

let puts: unknown[] = []

function stubServer(fail = false): void {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>().mockImplementation((_url, init) => {
      if (fail) return Promise.reject(new TypeError('offline'))
      if (init?.method === 'PUT') {
        puts.push(JSON.parse(String(init.body)))
        return Promise.resolve(new Response(String(init.body)))
      }
      return Promise.resolve(new Response(JSON.stringify(SERVER)))
    }),
  )
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  puts = []
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('cache settings on the server', () => {
  it('takes the server values over the local copy, without sending them back', async () => {
    stubServer()
    const prefs = usePrefs()
    expect(prefs.cacheInboxCount.value).toBe(200)
    await prefs.loadServerSettings()
    expect(prefs.cacheUnread.value).toBe(false)
    expect(prefs.cacheInboxCount.value).toBe(50)
    expect(prefs.cacheMaxAgeDays.value).toBe(7)
    await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    expect(puts).toEqual([])
  })

  it('sends a change once, after a short pause', async () => {
    stubServer()
    const prefs = usePrefs()
    await prefs.loadServerSettings()
    prefs.cacheInboxCount.value = 1
    await nextTick()
    prefs.cacheInboxCount.value = 10
    await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    expect(puts).toEqual([{ ...SERVER, cache_inbox_count: 10 }])
  })

  it('sends nothing before the server values are in, nor an empty number', async () => {
    stubServer()
    const prefs = usePrefs()
    prefs.cacheInbox.value = false
    await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    expect(puts).toEqual([])
    await prefs.loadServerSettings()
    prefs.cacheInboxCount.value = null as unknown as number
    await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    expect(puts).toEqual([])
  })

  it('keeps the local copy when the server cannot be reached', async () => {
    stubServer(true)
    const prefs = usePrefs()
    prefs.cacheMaxAgeDays.value = 3
    await prefs.loadServerSettings()
    expect(prefs.cacheMaxAgeDays.value).toBe(3)
  })
})
