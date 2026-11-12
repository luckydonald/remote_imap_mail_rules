import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/model/http'
import { moveMessage, setFlags } from '@/model/mail-api'
import { clearAll } from '@/model/offline/db'
import {
  enqueue,
  flush,
  loadQueue,
  queued,
  queueNotice,
  type QueueEntry,
} from '@/model/offline/queue'
import { setOnline } from '@/model/online'

vi.mock('@/model/mail-api', () => ({
  setFlags: vi.fn<typeof setFlags>(),
  moveMessage: vi.fn<typeof moveMessage>(),
}))

type Input = Omit<QueueEntry, 'id' | 'queuedAt' | 'after'>
const mail = { accountId: 'acc', folder: 'INBOX', uid: 7 }
const read: Input = { kind: 'flag', ...mail, add: ['\\Seen'], remove: [] }
const unread: Input = { kind: 'flag', ...mail, add: [], remove: ['\\Seen'] }
const move: Input = { kind: 'move', ...mail, add: [], remove: [], target: 'Archive' }
const summary = (): string[] =>
  queued.value.map((e) =>
    e.kind === 'move'
      ? `move ${e.target}`
      : `${e.add.length ? '+' : '-'}${[...e.add, ...e.remove]}${e.after ? ` after ${e.after}` : ''}`,
  )

beforeEach(async () => {
  vi.mocked(setFlags).mockReset().mockResolvedValue()
  vi.mocked(moveMessage).mockReset().mockResolvedValue({ folder: 'Archive', uid: 99 })
  await clearAll()
  queued.value = []
  queueNotice.value = ''
  setOnline(true)
})

describe('offline queue collapsing', () => {
  it('read then unread keeps only the later one', async () => {
    await enqueue(read)
    await enqueue(unread)
    expect(summary()).toEqual(['-\\Seen'])
  })

  it('unread then read keeps only the later one', async () => {
    await enqueue(unread)
    await enqueue(read)
    expect(summary()).toEqual(['+\\Seen'])
  })

  it('the same change twice is one entry', async () => {
    await enqueue(read)
    await enqueue(read)
    expect(summary()).toEqual(['+\\Seen'])
  })

  it('other mails are left alone', async () => {
    await enqueue(read)
    await enqueue({ ...unread, uid: 8 })
    expect(queued.value).toHaveLength(2)
  })

  it('other flags of the same mail are left alone', async () => {
    await enqueue(read)
    await enqueue({ kind: 'flag', ...mail, add: ['\\Flagged'], remove: [] })
    expect(summary()).toEqual(['+\\Seen', '+\\Flagged'])
  })

  it('a flag change before a move and the move both stay', async () => {
    await enqueue(read)
    await enqueue(move)
    expect(summary()).toEqual(['+\\Seen', 'move Archive'])
  })

  it('a second move replaces the first', async () => {
    await enqueue(move)
    await enqueue({ ...move, target: 'Trash' })
    expect(summary()).toEqual(['move Trash'])
  })

  it('a flag change after a move stays and follows the move', async () => {
    await enqueue(move)
    await enqueue(read)
    expect(summary()).toEqual(['move Archive', `+\\Seen after ${queued.value[0]!.id}`])
  })

  it('survives a reload from IndexedDB', async () => {
    await enqueue(read)
    queued.value = []
    await loadQueue()
    expect(summary()).toEqual(['+\\Seen'])
  })
})

describe('offline queue flush', () => {
  it('sends in order and empties the queue', async () => {
    await enqueue(read)
    await enqueue({ ...move, uid: 8 })
    await flush()
    expect(setFlags).toHaveBeenCalledWith('acc', 'INBOX', 7, { add: ['\\Seen'], remove: [] })
    expect(moveMessage).toHaveBeenCalledWith('acc', 'INBOX', 8, 'Archive')
    expect(queued.value).toEqual([])
    await loadQueue()
    expect(queued.value).toEqual([])
  })

  it('sends a flag after a move to the new folder and UID', async () => {
    await enqueue(move)
    await enqueue(read)
    await flush()
    expect(setFlags).toHaveBeenCalledWith('acc', 'Archive', 99, { add: ['\\Seen'], remove: [] })
  })

  it('drops the flag after a move when the server gives no new UID', async () => {
    vi.mocked(moveMessage).mockResolvedValue({ folder: 'Archive', uid: null })
    await enqueue(move)
    await enqueue(read)
    await flush()
    expect(setFlags).not.toHaveBeenCalled()
    expect(queued.value).toEqual([])
    expect(queueNotice.value).toContain('no new UID')
  })

  it('keeps everything on a network error and stops', async () => {
    vi.mocked(setFlags).mockRejectedValue(new TypeError('offline'))
    await enqueue(read)
    await enqueue({ ...read, uid: 8 })
    await flush()
    expect(setFlags).toHaveBeenCalledTimes(1)
    expect(queued.value).toHaveLength(2)
  })

  it('drops an entry whose mail is gone (404) and goes on', async () => {
    vi.mocked(setFlags).mockRejectedValueOnce(new ApiError(['No such message.'], 404))
    await enqueue(read)
    await enqueue({ ...read, uid: 8 })
    await flush()
    expect(setFlags).toHaveBeenCalledTimes(2)
    expect(queued.value).toEqual([])
  })

  it('drops the entry and tells once when actions are disabled (409)', async () => {
    vi.mocked(setFlags).mockRejectedValue(new ApiError(['actions_disabled'], 409))
    await enqueue(read)
    await flush()
    expect(queued.value).toEqual([])
    expect(queueNotice.value).toContain('ACTIONS_ENABLED')
  })

  it('stops at a login problem (401) and keeps the queue', async () => {
    vi.mocked(setFlags).mockRejectedValue(new ApiError(['Not logged in.'], 401))
    const unauthorized = vi.fn<() => void>()
    await enqueue(read)
    await flush(unauthorized)
    expect(unauthorized).toHaveBeenCalled()
    expect(queued.value).toHaveLength(1)
  })

  it('notes another error on the entry and keeps it', async () => {
    vi.mocked(setFlags).mockRejectedValue(new ApiError(['boom'], 500))
    await enqueue(read)
    await flush()
    expect(queued.value[0]!.error).toBe('boom')
  })
})
