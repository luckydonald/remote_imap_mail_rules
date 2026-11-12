/**
 * Actions done while offline: flag changes and moves, kept in IndexedDB and replayed in order when the server is back.
 * Per mail the later action wins over an earlier one of the same kind, see `enqueue`.
 */

import { ref } from 'vue'
import { ApiError } from '../http'
import { moveMessage, setFlags } from '../mail-api'
import { isNetworkError, setOnline } from '../online'
import { dbAll, dbDelete, dbPut } from './db'

export interface QueueEntry {
  id?: number
  kind: 'flag' | 'move'
  accountId: string
  folder: string
  uid: number
  add: string[]
  remove: string[]
  /** The target folder of a move. */
  target?: string
  /** A flag change that comes after a queued move of the same mail: it is sent to the moved mail, with the new folder and UID. */
  after?: number
  queuedAt: string
  error?: string
}

/** The queue as the screens see it; `loadQueue` fills it from IndexedDB. */
export const queued = ref<QueueEntry[]>([])
/** Tells the user about something that was dropped on the way; set by `flush`. */
export const queueNotice = ref('')

export async function loadQueue(): Promise<void> {
  const found = await dbAll<QueueEntry>('queue')
  queued.value = found.sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
}

const sameMail = (a: QueueEntry, b: Pick<QueueEntry, 'accountId' | 'folder' | 'uid'>): boolean =>
  a.accountId === b.accountId && a.folder === b.folder && a.uid === b.uid

async function save(entry: QueueEntry): Promise<void> {
  const key = await dbPut('queue', entry)
  if (typeof key === 'number') entry.id = key
}

async function drop(entry: QueueEntry): Promise<void> {
  if (entry.id !== undefined) await dbDelete('queue', entry.id)
  queued.value = queued.value.filter((item) => item !== entry)
}

/**
 * Adds an action and folds it into the ones queued for the same mail; the later one wins, nothing cancels both.
 * A flag change replaces the same flag of earlier entries (read, then unread: only unread stays) and an entry left with no flag is dropped.
 * A move replaces an earlier move of the mail. A flag change after a move stays, as `after` that move.
 */
export async function enqueue(
  input: Omit<QueueEntry, 'id' | 'queuedAt' | 'after'>,
  now = new Date(),
): Promise<void> {
  const entry: QueueEntry = { ...input, queuedAt: now.toISOString() }
  const mine = queued.value.filter((item) => sameMail(item, entry))
  const move = mine.find((item) => item.kind === 'move')
  if (entry.kind === 'move') {
    for (const old of mine.filter((item) => item.kind === 'move')) await drop(old)
  } else {
    if (move?.id !== undefined) entry.after = move.id
    const touched = new Set([...entry.add, ...entry.remove])
    for (const old of mine.filter((item) => item.kind === 'flag' && item.after === entry.after)) {
      old.add = old.add.filter((flag) => !touched.has(flag))
      old.remove = old.remove.filter((flag) => !touched.has(flag))
      if (old.add.length === 0 && old.remove.length === 0) await drop(old)
      else await save(old)
    }
  }
  await save(entry)
  queued.value = [...queued.value, entry].sort((a, b) => (a.id ?? 0) - (b.id ?? 0))
}

let flushing: Promise<void> | null = null

/** Sends the queue in order. Returns once it is empty or something stopped it (network, login); see `queueNotice`. */
export function flush(onUnauthorized: () => void = () => {}): Promise<void> {
  flushing ??= run(onUnauthorized).finally(() => {
    flushing = null
  })
  return flushing
}

async function run(onUnauthorized: () => void): Promise<void> {
  for (const entry of queued.value) {
    if (!queued.value.includes(entry)) continue
    try {
      if (entry.kind === 'flag') {
        await setFlags(entry.accountId, entry.folder, entry.uid, {
          add: entry.add,
          remove: entry.remove,
        })
      } else {
        const moved = await moveMessage(
          entry.accountId,
          entry.folder,
          entry.uid,
          entry.target ?? '',
        )
        const following = queued.value.filter((item) => item.after === entry.id)
        for (const item of following) {
          if (moved.uid === null) {
            queueNotice.value =
              'A move went through, but the server gave no new UID, so changes queued after it were dropped.'
            await drop(item)
          } else {
            item.folder = moved.folder
            item.uid = moved.uid
            item.after = undefined
            await save(item)
          }
        }
      }
      setOnline(true)
      await drop(entry)
    } catch (caught) {
      if (isNetworkError(caught)) {
        setOnline(false)
        return
      }
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized()
        return
      }
      if (caught instanceof ApiError && (caught.status === 404 || caught.status === 409)) {
        if (caught.status === 409)
          queueNotice.value =
            'The server does not apply changes (ACTIONS_ENABLED is off), queued changes were dropped.'
        // Entries after a dropped move have nothing to follow.
        for (const item of queued.value.filter((other) => other.after === entry.id))
          await drop(item)
        await drop(entry)
        continue
      }
      entry.error = caught instanceof Error ? caught.message : String(caught)
      await save(entry)
    }
  }
}
