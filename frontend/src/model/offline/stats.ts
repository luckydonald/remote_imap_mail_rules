/** What this browser keeps for offline use, for the stats page. A snapshot; without IndexedDB or the Cache API the numbers are 0. */

import { dbAll, type StoreName } from './db'

export interface StoreStats {
  store: StoreName
  records: number
  /** The size of the records as JSON, an estimate: IndexedDB does not tell its size per store. */
  bytes: number
}

export interface CacheStats {
  stores: StoreStats[]
  /** Cached mails per reason they are kept for (a mail can have several). */
  reasons: Record<string, number>
  /** The browser's own estimate for the whole origin, `null` when it has none. */
  usage: number | null
  quota: number | null
  /** Entries of the service worker caches (the precached build). */
  workerEntries: number
  /** Size of the localStorage entries as text. */
  localStorageBytes: number
}

const STORES: StoreName[] = ['folders', 'lists', 'details', 'queue']

const sizeOf = (value: unknown): number => JSON.stringify(value)?.length ?? 0

async function workerEntries(): Promise<number> {
  if (typeof caches === 'undefined') return 0
  let total = 0
  for (const name of await caches.keys()) total += (await (await caches.open(name)).keys()).length
  return total
}

function localStorageBytes(): number {
  if (typeof localStorage === 'undefined') return 0
  let total = 0
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index)
    if (key !== null) total += key.length + (localStorage.getItem(key)?.length ?? 0)
  }
  return total
}

export async function cacheStats(): Promise<CacheStats> {
  const stores: StoreStats[] = []
  const reasons: Record<string, number> = {}
  for (const store of STORES) {
    const records = await dbAll<{ reasons?: string[] }>(store)
    stores.push({ store, records: records.length, bytes: sizeOf(records) })
    if (store === 'details') {
      for (const record of records) {
        for (const reason of record.reasons ?? []) reasons[reason] = (reasons[reason] ?? 0) + 1
      }
    }
  }
  const estimate = (await navigator.storage?.estimate?.().catch(() => undefined)) ?? undefined
  return {
    stores,
    reasons,
    usage: estimate?.usage ?? null,
    quota: estimate?.quota ?? null,
    workerEntries: await workerEntries().catch(() => 0),
    localStorageBytes: localStorageBytes(),
  }
}
