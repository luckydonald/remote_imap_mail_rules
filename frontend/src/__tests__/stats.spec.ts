import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { clearAll, dbPut } from '@/model/offline/db'
import { cacheStats } from '@/model/offline/stats'

describe('cacheStats', () => {
  beforeEach(async () => {
    await clearAll()
  })

  it('counts the records of every store', async () => {
    await dbPut('folders', { key: 'a' })
    await dbPut('lists', { key: 'b' })
    await dbPut('lists', { key: 'c' })
    const stats = await cacheStats()
    const counts = Object.fromEntries(stats.stores.map((s) => [s.store, s.records]))
    expect(counts).toEqual({ folders: 1, lists: 2, details: 0, queue: 0 })
    expect(stats.stores.find((s) => s.store === 'lists')?.bytes).toBeGreaterThan(0)
  })

  it('counts the cached mails per reason', async () => {
    await dbPut('details', { key: '1', reasons: ['inbox', 'opened'] })
    await dbPut('details', { key: '2', reasons: ['inbox'] })
    expect((await cacheStats()).reasons).toEqual({ inbox: 2, opened: 1 })
  })

  it('has no usage without a storage estimate', async () => {
    const stats = await cacheStats()
    expect(stats.workerEntries).toBe(0)
    expect(stats.localStorageBytes).toBeGreaterThanOrEqual(0)
  })
})
