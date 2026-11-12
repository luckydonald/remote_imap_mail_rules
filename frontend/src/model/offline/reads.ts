/**
 * The read calls of the mail browser with the offline cache behind them: the network first (and written through),
 * the cache when the network fails. An answer of the server, even an error, is never replaced by the cache.
 */

import {
  getMessage,
  listFolders,
  listMessages,
  type BodyOptions,
  type Detail,
  type Folder,
  type Page,
} from '../mail-api'
import { listAccounts, type Account } from '../accounts-api'
import { isNetworkError, setOnline } from '../online'
import {
  loadAccounts,
  loadDetail,
  loadFolders,
  loadPage,
  saveAccounts,
  saveDetail,
  saveFolders,
  savePage,
  touchDetail,
  type CacheRules,
} from './cache'

export async function readAccounts(): Promise<Account[]> {
  try {
    const found = await listAccounts()
    setOnline(true)
    await saveAccounts(found)
    return found
  } catch (caught) {
    if (!isNetworkError(caught)) throw caught
    setOnline(false)
    const cached = await loadAccounts()
    if (cached) return cached
    throw caught
  }
}

export async function readFolders(accountId: string): Promise<Folder[]> {
  try {
    const found = await listFolders(accountId)
    setOnline(true)
    await saveFolders(accountId, found)
    return found
  } catch (caught) {
    if (!isNetworkError(caught)) throw caught
    setOnline(false)
    const cached = await loadFolders(accountId)
    if (cached) return cached
    throw caught
  }
}

export async function readPage(
  accountId: string,
  folder: string,
  before: number | null,
): Promise<Page> {
  try {
    const page = await listMessages(accountId, folder, before)
    setOnline(true)
    await savePage(accountId, folder, before, page)
    return page
  } catch (caught) {
    if (!isNetworkError(caught)) throw caught
    setOnline(false)
    const cached = await loadPage(accountId, folder, before)
    if (cached) return cached
    throw caught
  }
}

/** `opened` is true for a mail the user opened, false for a background prefetch. */
export async function readMail(
  accountId: string,
  folder: string,
  uid: number,
  options: BodyOptions,
  rules: CacheRules,
  opened = true,
): Promise<Detail> {
  try {
    const found = await getMessage(accountId, folder, uid, options)
    setOnline(true)
    await saveDetail(accountId, folder, found, rules, opened)
    return found
  } catch (caught) {
    if (!isNetworkError(caught)) throw caught
    setOnline(false)
    const cached = await loadDetail(accountId, folder, uid)
    if (cached) {
      await touchDetail(accountId, folder, uid)
      return cached
    }
    throw caught
  }
}
