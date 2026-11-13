/** A small IndexedDB wrapper for the offline cache. Without IndexedDB (tests, private modes) every call does nothing. */

export type StoreName = 'folders' | 'lists' | 'details' | 'queue'

const NAME = 'mail-offline'
const VERSION = 1
let opened: Promise<IDBDatabase | null> | null = null

function open(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === 'undefined') return Promise.resolve(null)
  opened ??= new Promise((resolve) => {
    const request = indexedDB.open(NAME, VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      db.createObjectStore('folders', { keyPath: 'key' })
      db.createObjectStore('lists', { keyPath: 'key' })
      db.createObjectStore('details', { keyPath: 'key' })
      db.createObjectStore('queue', { keyPath: 'id', autoIncrement: true })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => resolve(null)
  })
  return opened
}

async function run<T>(
  store: StoreName,
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
  fallback: T,
): Promise<T> {
  const db = await open()
  if (db === null) return fallback
  return new Promise((resolve) => {
    try {
      const request = action(db.transaction(store, mode).objectStore(store))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => resolve(fallback)
    } catch {
      resolve(fallback)
    }
  })
}

export const dbGet = <T>(store: StoreName, key: IDBValidKey): Promise<T | undefined> =>
  run<T | undefined>(store, 'readonly', (s) => s.get(key), undefined)
export const dbAll = <T>(store: StoreName): Promise<T[]> =>
  run<T[]>(store, 'readonly', (s) => s.getAll(), [])
export const dbCount = (store: StoreName): Promise<number> =>
  run<number>(store, 'readonly', (s) => s.count(), 0)
/** Stores a record and answers its key (the generated one for the queue). */
export const dbPut = (store: StoreName, value: object): Promise<IDBValidKey | undefined> =>
  run<IDBValidKey | undefined>(
    store,
    'readwrite',
    (s) => s.put(value) as IDBRequest<IDBValidKey | undefined>,
    undefined,
  )
export const dbDelete = (store: StoreName, key: IDBValidKey): Promise<undefined> =>
  run<undefined>(store, 'readwrite', (s) => s.delete(key), undefined)
export const dbClear = (store: StoreName): Promise<undefined> =>
  run<undefined>(store, 'readwrite', (s) => s.clear(), undefined)

/** Forgets everything, e.g. on log out. */
export async function clearAll(): Promise<void> {
  for (const store of ['folders', 'lists', 'details', 'queue'] as const) await dbClear(store)
}
