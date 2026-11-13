/**
 * The offline mail cache in IndexedDB: the folder tree, the message lists and the mails themselves.
 * A mail stays while some enabled rule claims it (`reasons`): `unread` (unread mail of a folder that was opened), `opened` (opened while unread),
 * `inbox` (one of the newest N of the INBOX). `purge` drops what no rule claims, and mails not viewed for a long time.
 */

import type { Account } from '../accounts-api'
import type { Detail, Folder, Page, Summary } from '../mail-api'
import { dbAll, dbDelete, dbGet, dbPut } from './db'

export type Reason = 'unread' | 'opened' | 'inbox'

export interface CacheRules {
  cacheUnread: boolean
  cacheOpenedUnread: boolean
  cacheInbox: boolean
  cacheInboxCount: number
  /** Mails not viewed for this many days are dropped (outside the INBOX window); 0 keeps them for ever. */
  cacheMaxAgeDays: number
}

export const PAGE_SIZE = 50
export const DAY_MS = 24 * 3600 * 1000

interface FoldersRecord {
  key: string
  accountId: string
  folders: Folder[]
  cachedAt: string
}

interface ListRecord {
  key: string
  accountId: string
  folder: string
  uidvalidity: number | null
  /** Newest first. */
  messages: Summary[]
  total: number
  nextBefore: number | null
}

interface DetailRecord {
  key: string
  accountId: string
  folder: string
  uid: number
  uidvalidity: number | null
  seen: boolean
  detail: Detail
  reasons: Reason[]
  cachedAt: string
  lastViewedAt: string
}

const listKey = (accountId: string, folder: string): string => `${accountId}|${folder}`
const detailKey = (accountId: string, folder: string, uid: number): string =>
  `${accountId}|${folder}|${uid}`
const isInbox = (folder: string): boolean => folder.toUpperCase() === 'INBOX'

/** The account list is kept next to the folder trees, under a key no account id can have. */
export async function saveAccounts(accounts: Account[]): Promise<void> {
  await dbPut('folders', {
    key: 'accounts',
    accounts: JSON.parse(JSON.stringify(accounts)) as Account[],
  })
}

export async function loadAccounts(): Promise<Account[] | null> {
  return (await dbGet<{ accounts: Account[] }>('folders', 'accounts'))?.accounts ?? null
}

export async function saveFolders(accountId: string, folders: Folder[]): Promise<void> {
  const record: FoldersRecord = {
    key: accountId,
    accountId,
    folders: JSON.parse(JSON.stringify(folders)) as Folder[],
    cachedAt: new Date().toISOString(),
  }
  await dbPut('folders', record)
}

export async function loadFolders(accountId: string): Promise<Folder[] | null> {
  return (await dbGet<FoldersRecord>('folders', accountId))?.folders ?? null
}

/** Forgets the cached lists and mails of a folder, e.g. when its UIDVALIDITY changed. */
export async function dropFolder(accountId: string, folder: string): Promise<void> {
  await dbDelete('lists', listKey(accountId, folder))
  for (const record of await dbAll<DetailRecord>('details')) {
    if (record.accountId === accountId && record.folder === folder)
      await dbDelete('details', record.key)
  }
}

/** Writes a page through; the first page (`before` null) replaces the list, a later one is appended. */
export async function savePage(
  accountId: string,
  folder: string,
  before: number | null,
  page: Page,
): Promise<void> {
  const key = listKey(accountId, folder)
  const old = await dbGet<ListRecord>('lists', key)
  const validity = page.uidvalidity ?? page.messages[0]?.uidvalidity ?? null
  if (old && validity !== null && old.uidvalidity !== null && old.uidvalidity !== validity)
    await dropFolder(accountId, folder)
  const keep = before !== null && old && old.uidvalidity === validity ? old.messages : []
  const seen = new Set(keep.map((item) => item.uid))
  const messages = [...keep, ...page.messages.filter((item) => !seen.has(item.uid))]
  const record: ListRecord = {
    key,
    accountId,
    folder,
    uidvalidity: validity,
    messages: JSON.parse(JSON.stringify(messages)) as Summary[],
    total: page.total,
    nextBefore: page.next_before_uid,
  }
  await dbPut('lists', record)
  // A mail seen on the server since it was cached no longer counts as unread.
  for (const item of page.messages) {
    const cached = await dbGet<DetailRecord>('details', detailKey(accountId, folder, item.uid))
    if (cached && cached.seen !== item.seen) await dbPut('details', { ...cached, seen: item.seen })
  }
}

/** The cached page below `before`, or `null` when this folder was never cached. */
export async function loadPage(
  accountId: string,
  folder: string,
  before: number | null,
): Promise<Page | null> {
  const record = await dbGet<ListRecord>('lists', listKey(accountId, folder))
  if (!record) return null
  const older = record.messages.filter((item) => before === null || item.uid < before)
  const messages = older.slice(0, PAGE_SIZE)
  const more = older.length > PAGE_SIZE
  const last = messages[messages.length - 1]
  return {
    messages,
    total: record.total,
    next_before_uid:
      more && last ? last.uid : more ? null : before === null ? record.nextBefore : null,
    uidvalidity: record.uidvalidity,
  }
}

/** Which rules claim a mail right now. `rank` is its place among the newest mails of the folder (0 is the newest). */
export function reasonsFor(
  rules: CacheRules,
  folder: string,
  seen: boolean,
  opened: boolean,
  rank: number | null,
): Reason[] {
  const reasons: Reason[] = []
  if (rules.cacheUnread && !seen && !isInbox(folder)) reasons.push('unread')
  if (rules.cacheOpenedUnread && opened && !seen) reasons.push('opened')
  if (rules.cacheInbox && isInbox(folder) && rank !== null && rank < rules.cacheInboxCount)
    reasons.push('inbox')
  return reasons
}

/** Writes a mail through. `opened` is true when the user opened it (not a background prefetch). */
export async function saveDetail(
  accountId: string,
  folder: string,
  detail: Detail,
  rules: CacheRules,
  opened: boolean,
  now = new Date(),
): Promise<void> {
  const key = detailKey(accountId, folder, detail.uid)
  const old = await dbGet<DetailRecord>('details', key)
  const list = await dbGet<ListRecord>('lists', listKey(accountId, folder))
  const index = list ? list.messages.findIndex((item) => item.uid === detail.uid) : -1
  const wasOpened = opened || (old?.reasons.includes('opened') ?? false)
  const reasons = reasonsFor(rules, folder, detail.seen, wasOpened, index >= 0 ? index : null)
  if (reasons.length === 0) return
  const stamp = now.toISOString()
  const record: DetailRecord = {
    key,
    accountId,
    folder,
    uid: detail.uid,
    uidvalidity: detail.uidvalidity ?? list?.uidvalidity ?? null,
    seen: detail.seen,
    detail: JSON.parse(JSON.stringify(detail)) as Detail,
    reasons,
    cachedAt: old?.cachedAt ?? stamp,
    lastViewedAt: opened ? stamp : (old?.lastViewedAt ?? stamp),
  }
  await dbPut('details', record)
}

export async function loadDetail(
  accountId: string,
  folder: string,
  uid: number,
): Promise<Detail | null> {
  const record = await dbGet<DetailRecord>('details', detailKey(accountId, folder, uid))
  return record?.detail ?? null
}

/** Notes that the user looked at a cached mail. */
export async function touchDetail(
  accountId: string,
  folder: string,
  uid: number,
  now = new Date(),
): Promise<void> {
  const record = await dbGet<DetailRecord>('details', detailKey(accountId, folder, uid))
  if (record) await dbPut('details', { ...record, lastViewedAt: now.toISOString() })
}

/** Applies a read/unread change or a move done by the user to the cache. */
export async function markSeen(
  accountId: string,
  folder: string,
  uid: number,
  seen: boolean,
): Promise<void> {
  const record = await dbGet<DetailRecord>('details', detailKey(accountId, folder, uid))
  if (record) {
    const flags = seen
      ? [...new Set([...record.detail.flags, '\\Seen'])]
      : record.detail.flags.filter((flag) => flag !== '\\Seen')
    await dbPut('details', { ...record, seen, detail: { ...record.detail, seen, flags } })
  }
  const list = await dbGet<ListRecord>('lists', listKey(accountId, folder))
  const row = list?.messages.find((item) => item.uid === uid)
  if (list && row) {
    row.seen = seen
    await dbPut('lists', list)
  }
}

/** Removes a mail that left its folder. */
export async function removeMail(accountId: string, folder: string, uid: number): Promise<void> {
  await dbDelete('details', detailKey(accountId, folder, uid))
  const list = await dbGet<ListRecord>('lists', listKey(accountId, folder))
  if (list) {
    list.messages = list.messages.filter((item) => item.uid !== uid)
    list.total = Math.max(0, list.total - 1)
    await dbPut('lists', list)
  }
}

/** UIDs of a folder that a background prefetch should fetch, by the rules: the INBOX window and unread mails of opened folders (not the INBOX). */
export async function wanted(
  accountId: string,
  rules: CacheRules,
): Promise<{ folder: string; uid: number }[]> {
  const found: { folder: string; uid: number }[] = []
  for (const list of await dbAll<ListRecord>('lists')) {
    if (list.accountId !== accountId) continue
    list.messages.forEach((item, rank) => {
      if (reasonsFor(rules, list.folder, item.seen, false, rank).length > 0)
        found.push({ folder: list.folder, uid: item.uid })
    })
  }
  const have = new Set((await dbAll<DetailRecord>('details')).map((record) => record.key))
  return found.filter((item) => !have.has(detailKey(accountId, item.folder, item.uid)))
}

/** Drops what no enabled rule claims any more, and mails not viewed for `MAX_AGE_MS` that are not in the INBOX window. */
export async function purge(rules: CacheRules, now = new Date()): Promise<number> {
  const lists = new Map((await dbAll<ListRecord>('lists')).map((list) => [list.key, list]))
  let removed = 0
  for (const record of await dbAll<DetailRecord>('details')) {
    const list = lists.get(listKey(record.accountId, record.folder))
    const rank = list ? list.messages.findIndex((item) => item.uid === record.uid) : -1
    const row = rank >= 0 ? list?.messages[rank] : undefined
    const seen = row ? row.seen : record.seen
    const opened = record.reasons.includes('opened')
    const reasons = reasonsFor(rules, record.folder, seen, opened, rank >= 0 ? rank : null)
    const old =
      rules.cacheMaxAgeDays > 0 &&
      now.getTime() - new Date(record.lastViewedAt).getTime() > rules.cacheMaxAgeDays * DAY_MS
    if (reasons.length === 0 || (old && !reasons.includes('inbox'))) {
      await dbDelete('details', record.key)
      removed += 1
    } else if (reasons.join() !== record.reasons.join()) {
      await dbPut('details', { ...record, reasons, seen })
    }
  }
  return removed
}
