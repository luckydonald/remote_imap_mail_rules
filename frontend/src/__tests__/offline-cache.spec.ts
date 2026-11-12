import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import type { Detail, Folder, Page, Summary } from '@/model/mail-api'
import {
  loadDetail,
  loadFolders,
  loadPage,
  markSeen,
  purge,
  removeMail,
  saveDetail,
  savePage,
  saveFolders,
  touchDetail,
  wanted,
  type CacheRules,
} from '@/model/offline/cache'
import { clearAll, dbAll } from '@/model/offline/db'
import { mergeFolders } from '@/model/store/mail'

const RULES: CacheRules = {
  cacheUnread: true,
  cacheOpenedUnread: true,
  cacheInbox: true,
  cacheInboxCount: 2,
  cacheMaxAgeDays: 30,
}
const summary = (uid: number, seen = false): Summary => ({
  uid,
  sender: { name: 'Max', address: 'max@example.com' },
  subject: `mail ${uid}`,
  date: null,
  seen,
  flagged: false,
  answered: false,
  has_attachments: false,
  size: 1,
  uidvalidity: 5,
})
const detail = (uid: number, seen = false): Detail =>
  ({
    ...summary(uid, seen),
    flags: seen ? ['\\Seen'] : [],
    text: `body ${uid}`,
  }) as unknown as Detail
const page = (uids: number[], seen: number[] = [], extra: Partial<Page> = {}): Page => ({
  messages: uids.map((uid) => summary(uid, seen.includes(uid))),
  total: uids.length,
  next_before_uid: null,
  uidvalidity: 5,
  ...extra,
})
const DAY = 24 * 3600 * 1000
const keys = async (): Promise<string[]> =>
  (await dbAll<{ key: string }>('details')).map((r) => r.key).sort()

beforeEach(async () => {
  await clearAll()
})

describe('offline cache', () => {
  it('writes a list through and reads it back in pages', async () => {
    const uids = Array.from({ length: 120 }, (_, i) => 120 - i)
    await savePage('a', 'INBOX', null, page(uids.slice(0, 50), [], { next_before_uid: 71 }))
    await savePage('a', 'INBOX', 71, page(uids.slice(50, 100), [], { next_before_uid: 21 }))
    const first = await loadPage('a', 'INBOX', null)
    expect(first!.messages).toHaveLength(50)
    expect(first!.next_before_uid).toBe(71)
    const second = await loadPage('a', 'INBOX', 71)
    expect(second!.messages[0]!.uid).toBe(70)
    expect(await loadPage('a', 'Sent', null)).toBeNull()
  })

  it('keeps unread mails and drops them once read, except the INBOX window', async () => {
    await savePage('a', 'Work', null, page([3, 2, 1]))
    for (const uid of [1, 2]) await saveDetail('a', 'Work', detail(uid), RULES, false)
    expect(await keys()).toEqual(['a|Work|1', 'a|Work|2'])
    await markSeen('a', 'Work', 1, true)
    await purge(RULES)
    expect(await keys()).toEqual(['a|Work|2'])
  })

  it('keeps the newest N INBOX mails even when read', async () => {
    await savePage('a', 'INBOX', null, page([4, 3, 2, 1], [4, 3, 2, 1]))
    for (const uid of [4, 3, 2]) await saveDetail('a', 'INBOX', detail(uid, true), RULES, false)
    expect(await keys()).toEqual(['a|INBOX|3', 'a|INBOX|4'])
  })

  it('each rule works on its own', async () => {
    const off: CacheRules = {
      cacheMaxAgeDays: 30,
      cacheUnread: false,
      cacheOpenedUnread: false,
      cacheInbox: false,
      cacheInboxCount: 2,
    }
    await savePage('a', 'INBOX', null, page([2, 1]))
    await saveDetail('a', 'INBOX', detail(2), off, false)
    expect(await keys()).toEqual([])
    await saveDetail('a', 'INBOX', detail(2), { ...off, cacheUnread: true }, false)
    await saveDetail('a', 'INBOX', detail(1), { ...off, cacheInbox: true }, false)
    await saveDetail('a', 'Other', detail(9), { ...off, cacheOpenedUnread: true }, true)
    expect(await keys()).toEqual(['a|INBOX|1', 'a|INBOX|2', 'a|Other|9'])
  })

  it('a mail opened while unread is kept without its list, and leaves when read', async () => {
    await saveDetail('a', 'Far', detail(5), RULES, true)
    expect(await loadDetail('a', 'Far', 5)).not.toBeNull()
    await markSeen('a', 'Far', 5, true)
    await purge(RULES)
    expect(await loadDetail('a', 'Far', 5)).toBeNull()
  })

  it('turning a rule off drops its mails on the next purge', async () => {
    await savePage('a', 'Work', null, page([1]))
    await saveDetail('a', 'Work', detail(1), RULES, false)
    await purge({ ...RULES, cacheUnread: false })
    expect(await keys()).toEqual([])
  })

  it('a mail seen on the server drops out after the list reload', async () => {
    await savePage('a', 'Work', null, page([1]))
    await saveDetail('a', 'Work', detail(1), RULES, false)
    await savePage('a', 'Work', null, page([1], [1]))
    await purge(RULES)
    expect(await keys()).toEqual([])
  })

  it('records when a mail was cached and last viewed, and purges the old ones', async () => {
    const t0 = new Date('2026-01-01T00:00:00Z')
    await saveDetail('a', 'Far', detail(5), RULES, true, t0)
    await touchDetail('a', 'Far', 5, new Date(t0.getTime() + 10 * DAY))
    const [record] = await dbAll<{ cachedAt: string; lastViewedAt: string }>('details')
    expect(record!.cachedAt).toBe(t0.toISOString())
    expect(record!.lastViewedAt).toBe(new Date(t0.getTime() + 10 * DAY).toISOString())
    await purge(RULES, new Date(t0.getTime() + 30 * DAY))
    expect(await keys()).toHaveLength(1)
    await purge(RULES, new Date(t0.getTime() + 41 * DAY))
    expect(await keys()).toEqual([])
  })

  it('the age comes from the setting, and 0 never purges by age', async () => {
    const t0 = new Date('2026-01-01T00:00:00Z')
    await saveDetail('a', 'Far', detail(5), RULES, true, t0)
    await purge({ ...RULES, cacheMaxAgeDays: 7 }, new Date(t0.getTime() + 8 * DAY))
    expect(await keys()).toEqual([])
    await saveDetail('a', 'Far', detail(5), RULES, true, t0)
    await purge({ ...RULES, cacheMaxAgeDays: 0 }, new Date(t0.getTime() + 900 * DAY))
    expect(await keys()).toEqual(['a|Far|5'])
  })

  it('old mails in the INBOX window stay', async () => {
    const t0 = new Date('2026-01-01T00:00:00Z')
    await savePage('a', 'INBOX', null, page([2, 1], [2, 1]))
    await saveDetail('a', 'INBOX', detail(2, true), RULES, false, t0)
    await purge(RULES, new Date(t0.getTime() + 90 * DAY))
    expect(await keys()).toEqual(['a|INBOX|2'])
  })

  it('records every rule that holds a mail', async () => {
    await savePage('a', 'INBOX', null, page([2, 1]))
    await saveDetail('a', 'INBOX', detail(2), RULES, true)
    const [record] = await dbAll<{ reasons: string[] }>('details')
    expect(record!.reasons).toEqual(['unread', 'opened', 'inbox'])
  })

  it('drops a folder when its UIDVALIDITY changed', async () => {
    await savePage('a', 'Work', null, page([1]))
    await saveDetail('a', 'Work', detail(1), RULES, false)
    await savePage('a', 'Work', null, page([1], [], { uidvalidity: 6 }))
    expect(await loadDetail('a', 'Work', 1)).toBeNull()
    expect((await loadPage('a', 'Work', null))!.uidvalidity).toBe(6)
  })

  it('removes a moved mail from its list and cache', async () => {
    await savePage('a', 'Work', null, page([2, 1]))
    await saveDetail('a', 'Work', detail(1), RULES, false)
    await removeMail('a', 'Work', 1)
    expect(await loadDetail('a', 'Work', 1)).toBeNull()
    expect((await loadPage('a', 'Work', null))!.messages.map((m) => m.uid)).toEqual([2])
  })

  it('lists the mails a prefetch still needs', async () => {
    await savePage('a', 'INBOX', null, page([3, 2, 1], [3, 2, 1]))
    await saveDetail('a', 'INBOX', detail(3, true), RULES, false)
    expect(await wanted('a', RULES)).toEqual([{ folder: 'INBOX', uid: 2 }])
  })

  it('keeps the folder tree per account', async () => {
    const folder: Folder = {
      name: 'INBOX',
      display_name: 'INBOX',
      delimiter: '/',
      special_use: 'inbox',
      selectable: true,
      messages: 1,
      unseen: 1,
    }
    await saveFolders('a', [folder])
    expect(await loadFolders('a')).toEqual([folder])
    expect(await loadFolders('b')).toBeNull()
  })
})

describe('folder tree refresh', () => {
  const f = (name: string, unseen: number): Folder => ({
    name,
    display_name: name,
    delimiter: '/',
    special_use: null,
    selectable: true,
    messages: 5,
    unseen,
  })

  it('updates in place: kept entries stay the same objects, new ones appear, gone ones leave', () => {
    const list = [f('A', 1), f('B', 2)]
    const a = list[0]!
    mergeFolders(list, [f('A', 9), f('C', 0)])
    expect(list.map((x) => x.name)).toEqual(['A', 'C'])
    expect(list[0]).toBe(a)
    expect(a.unseen).toBe(9)
  })
})
