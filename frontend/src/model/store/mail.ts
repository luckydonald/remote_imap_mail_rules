/** State of the mail browser: accounts, folders, the paged message list and the open message. Part of the central store (`index.ts`). */

import { computed, ref, watch } from 'vue'
import { listAccounts, type Account } from '../accounts-api'
import type { MailContext } from '../fill-from-mail'
import { ApiError, describeError } from '../http'
import type { usePrefs } from './prefs'
import { isNetworkError, onReconnect, setOnline, useOnline } from '../online'
import {
  loadDetail,
  loadFolders,
  markSeen,
  purge,
  removeMail,
  wanted,
  type CacheRules,
} from '../offline/cache'
import { readAccounts, readFolders, readMail, readPage } from '../offline/reads'
import { enqueue, flush, loadQueue, queued, queueNotice } from '../offline/queue'
import {
  listEvents,
  moveMessage,
  setFlags,
  type BodyOptions,
  type Detail,
  type Folder,
  type MailEvent,
  type Summary,
} from '../mail-api'

/** On a narrow screen only one of the panes shows. */
export type Pane = 'folders' | 'list' | 'message'

const STORAGE_KEY = 'mail-browser'

/** Where the browser is: account, folder and open mail, each `null` while not chosen. */
export interface Place {
  accountId: string | null
  folder: string | null
  uid: number | null
}

/** What survives a reload: the place, never credentials. The open mail itself comes from the offline cache. */
interface Saved {
  accountId: string | null
  folder: string | null
  uid: number | null
}

/** How often the folder tree is fetched again and the cache is topped up and purged. */
const REFRESH_MS = 5 * 60 * 1000
/** Mails fetched at the same time by the background prefetch. */
const PREFETCH_POOL = 4

/** Updates `target` in place from `fresh` (by name), so the open selection and what the views hold stay reactive. */
export function mergeFolders(target: Folder[], fresh: Folder[]): void {
  const old = new Map(target.map((item) => [item.name, item]))
  const merged = fresh.map((item) => {
    const kept = old.get(item.name)
    return kept ? Object.assign(kept, item) : item
  })
  target.splice(0, target.length, ...merged)
}

function readSaved(): Saved | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Saved) : null
  } catch {
    return null
  }
}

function writeSaved(saved: Saved): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
  } catch {
    // Storage can be blocked or full, the browser then just starts fresh next time.
  }
}

export function useMail(prefs: ReturnType<typeof usePrefs>) {
  let onUnauthorized: () => void = () => {}
  // The place of the last session, used once by the first loadAccounts().
  let restore = readSaved()
  const accounts = ref<Account[]>([])
  const accountId = ref<string | null>(null)
  const folders = ref<Folder[]>([])
  const folder = ref<string | null>(null)
  const messages = ref<Summary[]>([])
  const total = ref(0)
  const nextBefore = ref<number | null>(null)
  const detail = ref<Detail | null>(null)
  const selectedUid = ref<number | null>(restore?.uid ?? null)
  // The action log of the open mail; a failing log never hides the mail itself.
  const events = ref<MailEvent[]>([])
  // The log needs the server; offline the mail screen says so instead of showing an empty log.
  const eventsOffline = ref(false)
  const { isOnline } = useOnline()
  const error = ref('')
  const loading = ref(false)
  // True from the start until the accounts and the folders of the first account are in.
  const foldersLoading = ref(true)
  const pane = ref<Pane>('folders')
  // The side panel of the rule editor, and whether a server answers at all (see the context below).
  const panelOpen = ref(false)
  const active = ref(false)
  // Whether the server applies the actions of matching rules (`ACTIONS_ENABLED`); the dry run works either way.
  const actionsEnabled = ref(false)
  // What the HTML of the open mail may load; starts from the settings and is raised per mail by "Load remote images" / "Load styles".
  const bodyOptions = ref<BodyOptions>({})
  // Answers of requests that were overtaken by a newer choice are dropped.
  let listTicket = 0
  let detailTicket = 0
  let eventsTicket = 0

  const hasMore = computed(() => nextBefore.value !== null)
  /** The open mail with its place, for filling conditions; `null` offline or while no mail is open. */
  const context = computed<MailContext | null>(() => {
    const id = accountId.value ?? restore?.accountId ?? null
    const name = folder.value ?? restore?.folder ?? null
    if (!active.value || !detail.value || id === null || name === null) return null
    return { detail: detail.value, accountId: id, folder: name }
  })
  // The rule editor stops filling from the open mail (the chip's ×) while the mail itself stays open for the mail screens.
  const fillDetached = ref(false)
  /** What the rule editor fills conditions from: the open mail, unless the chip removed it. */
  const fillContext = computed<MailContext | null>(() =>
    fillDetached.value ? null : context.value,
  )
  const currentFolder = computed(() => folders.value.find((item) => item.name === folder.value))

  watch([accountId, folder, selectedUid, detail], () => {
    // While the restore is pending the refs are not the saved place yet, so nothing is overwritten.
    if (restore === null) {
      writeSaved({
        accountId: accountId.value,
        folder: folder.value,
        uid: selectedUid.value,
      })
    }
  })

  /** What the offline cache keeps, from the settings. */
  function cacheRules(): CacheRules {
    return {
      cacheUnread: prefs.cacheUnread.value,
      cacheOpenedUnread: prefs.cacheOpenedUnread.value,
      cacheInbox: prefs.cacheInbox.value,
      cacheInboxCount: prefs.cacheInboxCount.value,
    }
  }

  /** Puts a folder list in, in place when there already is one. */
  function applyFolders(found: Folder[]): void {
    const selectable = found.filter((item) => item.selectable)
    if (folders.value.length === 0) folders.value = selectable
    else mergeFolders(folders.value, selectable)
  }

  /** Leaves the open account, folder and mail, e.g. when the account is gone. */
  function resetPlace(): void {
    accountId.value = null
    folders.value = []
    folder.value = null
    messages.value = []
    total.value = 0
    nextBefore.value = null
    detail.value = null
    events.value = []
    selectedUid.value = null
  }

  /** Forgets everything of the session, e.g. on log out. */
  function clear(): void {
    stopOffline()
    restore = null
    accounts.value = []
    resetPlace()
    error.value = ''
    pane.value = 'folders'
    panelOpen.value = false
    fillDetached.value = false
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Nothing to forget when the storage is blocked.
    }
  }

  function setUnauthorizedHandler(handler: () => void): void {
    onUnauthorized = handler
  }

  function fail(prefix: string, caught: unknown): void {
    if (caught instanceof ApiError && caught.status === 401) {
      onUnauthorized()
      return
    }
    error.value = `${prefix}: ${describeError(caught)}`
  }

  /** `target` is the place a URL asks for, which wins over the one of the last session. */
  async function loadAccounts(target?: Place): Promise<void> {
    if (target?.accountId) restore = { ...target, accountId: target.accountId }
    try {
      accounts.value = await readAccounts()
      const saved = restore
      const wanted =
        accounts.value.find((item) => item.id === saved?.accountId) ?? accounts.value[0]
      if (accountId.value === null && wanted)
        await selectAccount(wanted.id, wanted.id === saved?.accountId)
      else foldersLoading.value = false
    } catch (caught) {
      foldersLoading.value = false
      fail('Could not load the accounts', caught)
    }
  }

  /**
   * Reads the accounts again, e.g. after the accounts screen changed them; unlike `loadAccounts` it opens nothing.
   * `renamed` tells that an account got another id, so the open account follows it instead of being treated as deleted.
   * Failures other than a login are thrown for the caller to show.
   */
  async function refreshAccounts(renamed?: { from: string; to: string }): Promise<void> {
    let list: Account[]
    try {
      list = await listAccounts()
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized()
        return
      }
      throw caught
    }
    accounts.value = list
    if (renamed && accountId.value === renamed.from) accountId.value = renamed.to
    if (accountId.value !== null && !list.some((item) => item.id === accountId.value)) {
      resetPlace()
      restore = null
      const first = list[0]
      if (first) await selectAccount(first.id)
    }
  }

  /** `keepPlace` brings back the folder and the open mail of the last session. */
  async function selectAccount(id: string, keepPlace = false): Promise<void> {
    const saved = keepPlace ? restore : null
    restore = null
    accountId.value = id
    folders.value = []
    folder.value = null
    messages.value = []
    if (!saved) {
      detail.value = null
      selectedUid.value = null
    }
    error.value = ''
    pane.value = 'folders'
    foldersLoading.value = true
    try {
      // The cached tree shows at once, the server's one replaces it in place.
      const cached = await loadFolders(id)
      if (cached && accountId.value === id && folders.value.length === 0) {
        applyFolders(cached)
        foldersLoading.value = false
      }
      const found = await readFolders(id)
      if (accountId.value !== id) return
      applyFolders(found)
      foldersLoading.value = false
      const inbox = folders.value.find((item) => item.special_use === 'inbox')
      const back = folders.value.find((item) => item.name === saved?.folder)
      if (back) {
        await selectFolder(back.name, saved?.uid ?? null)
      } else if (inbox) {
        detail.value = null
        selectedUid.value = null
        await selectFolder(inbox.name)
      }
    } catch (caught) {
      fail('Could not load the folders', caught)
    } finally {
      if (accountId.value === id) foldersLoading.value = false
    }
  }

  /** `uid` reopens that mail of the folder, e.g. after a reload. */
  async function selectFolder(name: string, uid: number | null = null): Promise<void> {
    if (accountId.value === null) return
    folder.value = name
    messages.value = []
    total.value = 0
    nextBefore.value = null
    detail.value = null
    selectedUid.value = null
    error.value = ''
    loading.value = false
    pane.value = 'list'
    // The mail only loads once the folders (already in) and the list are, so it never shows before them.
    await loadMore()
    if (uid !== null && folder.value === name && accountId.value !== null) await openMessage(uid)
  }

  // The background work of the offline cache: top up, purge, refresh the folder tree, send the queue.
  let backgroundTimer: ReturnType<typeof setInterval> | null = null
  let stopReconnect: (() => void) | null = null
  let prefetching = false

  /** Fetches the mails the cache rules want but do not have yet, a few at a time. */
  async function prefetch(): Promise<void> {
    if (prefetching || !isOnline.value) return
    prefetching = true
    try {
      const rules = cacheRules()
      for (const account of accounts.value) {
        if (rules.cacheInbox) {
          // The INBOX window needs the list down to the Nth mail.
          let before: number | null = null
          let have = 0
          while (isOnline.value && have < rules.cacheInboxCount) {
            const page = await readPage(account.id, 'INBOX', before)
            have += page.messages.length
            before = page.next_before_uid
            if (before === null) break
          }
        }
        const todo = await wanted(account.id, rules)
        let next = 0
        const worker = async (): Promise<void> => {
          while (isOnline.value && next < todo.length) {
            const item = todo[next++]!
            try {
              await readMail(account.id, item.folder, item.uid, {}, rules, false)
            } catch (caught) {
              if (isNetworkError(caught)) return
              // A mail that is gone or fails is skipped.
            }
          }
        }
        await Promise.all(Array.from({ length: PREFETCH_POOL }, worker))
      }
    } catch {
      // Prefetching is best effort, the next round tries again.
    } finally {
      prefetching = false
    }
  }

  /** Sends the queued actions of the offline time. */
  async function sendQueue(): Promise<void> {
    await flush(onUnauthorized)
  }

  /** One round of the background work. */
  async function background(): Promise<void> {
    await purge(cacheRules())
    if (!isOnline.value) return
    await sendQueue()
    await reloadFolders()
    await prefetch()
  }

  /** Brings the mail of the last session back from the offline cache (or the server), so the rule editor can fill from it without the mail screen being open. */
  async function restoreOpenMail(): Promise<void> {
    const saved = restore
    if (!saved?.accountId || saved.folder === null || saved.uid === null) return
    const ticket = ++detailTicket
    try {
      const found =
        (await loadDetail(saved.accountId, saved.folder, saved.uid)) ??
        (await readMail(saved.accountId, saved.folder, saved.uid, {}, cacheRules(), false))
      if (ticket === detailTicket && detail.value === null) detail.value = found
    } catch {
      // The mail screen reports a mail that cannot be loaded when it is opened.
    }
  }
  void restoreOpenMail()

  /** Starts the cache's background work once the accounts are known; call after login. */
  function startOffline(): void {
    void loadQueue()
    stopReconnect ??= onReconnect(() => void background())
    if (backgroundTimer === null) backgroundTimer = setInterval(() => void background(), REFRESH_MS)
    void background()
  }

  function stopOffline(): void {
    if (backgroundTimer !== null) clearInterval(backgroundTimer)
    backgroundTimer = null
    stopReconnect?.()
    stopReconnect = null
  }

  /** Loads the next page below the oldest mail shown; the first page when the list is empty. */
  async function loadMore(): Promise<void> {
    const id = accountId.value
    const name = folder.value
    if (id === null || name === null || loading.value) return
    const ticket = ++listTicket
    loading.value = true
    try {
      const before = messages.value.length > 0 ? nextBefore.value : null
      if (messages.value.length > 0 && before === null) return
      const page = await readPage(id, name, before)
      if (ticket !== listTicket) return
      messages.value = [...messages.value, ...page.messages]
      total.value = page.total
      nextBefore.value = page.next_before_uid
    } catch (caught) {
      if (ticket === listTicket) fail('Could not load the messages', caught)
    } finally {
      if (ticket === listTicket) loading.value = false
    }
  }

  /** Fetches the folders again (unseen counts, new folders); folder and open mail stay. */
  async function reloadFolders(): Promise<void> {
    const id = accountId.value
    if (id === null || foldersLoading.value) return
    foldersLoading.value = true
    try {
      const found = await readFolders(id)
      if (accountId.value === id) applyFolders(found)
    } catch (caught) {
      if (accountId.value === id) fail('Could not reload the folders', caught)
    } finally {
      if (accountId.value === id) foldersLoading.value = false
    }
  }

  /** Fetches the first page of the folder again and swaps it in; the list stays and the open mail stays open. */
  async function reloadMessages(): Promise<void> {
    const id = accountId.value
    const name = folder.value
    if (id === null || name === null || loading.value) return
    const ticket = ++listTicket
    loading.value = true
    try {
      const page = await readPage(id, name, null)
      if (ticket !== listTicket) return
      messages.value = page.messages
      total.value = page.total
      nextBefore.value = page.next_before_uid
    } catch (caught) {
      if (ticket === listTicket) fail('Could not reload the messages', caught)
    } finally {
      if (ticket === listTicket) loading.value = false
    }
  }

  async function openMessage(uid: number): Promise<void> {
    const id = accountId.value
    const name = folder.value
    if (id === null || name === null) return
    const ticket = ++detailTicket
    selectedUid.value = uid
    fillDetached.value = false
    detail.value = null
    events.value = []
    error.value = ''
    pane.value = 'message'
    bodyOptions.value = {
      remoteImages: prefs.remoteImages.value === 'allow',
      styles: prefs.mailStyles.value === 'allow',
    }
    void loadEvents(id, name, uid)
    try {
      const found = await readMail(id, name, uid, bodyOptions.value, cacheRules())
      if (ticket === detailTicket) detail.value = found
    } catch (caught) {
      if (ticket === detailTicket) fail('Could not load the message', caught)
    }
  }

  /** Loads the open mail again with more allowed, e.g. its remote images; the old body stays until the new one is in. */
  async function allow(options: BodyOptions): Promise<void> {
    const id = accountId.value
    const name = folder.value
    const uid = selectedUid.value
    if (id === null || name === null || uid === null) return
    const ticket = ++detailTicket
    bodyOptions.value = { ...bodyOptions.value, ...options }
    try {
      const found = await readMail(id, name, uid, bodyOptions.value, cacheRules())
      if (ticket === detailTicket) detail.value = found
    } catch (caught) {
      if (ticket === detailTicket) fail('Could not load the message', caught)
    }
  }

  /** Keeps the number badges of the folder list right after a mail was read, unread or moved. */
  function countUnseen(name: string | null, by: number): void {
    const entry = folders.value.find((item) => item.name === name)
    if (entry && entry.unseen !== null) entry.unseen = Math.max(0, entry.unseen + by)
  }

  /** Marks the open mail read or unread on the server. */
  async function setSeen(seen: boolean): Promise<void> {
    const id = accountId.value
    const name = folder.value
    const open = detail.value
    if (id === null || name === null || open === null || open.seen === seen) return
    const flag = '\\Seen'
    const change = seen ? { add: [flag], remove: [] } : { add: [], remove: [flag] }
    try {
      await setFlags(id, name, open.uid, change)
      setOnline(true)
    } catch (caught) {
      if (!isNetworkError(caught)) {
        fail('Could not change the mail', caught)
        return
      }
      // No connection: the change waits in the queue and is sent when the server is back.
      setOnline(false)
      await enqueue({ kind: 'flag', accountId: id, folder: name, uid: open.uid, ...change })
    }
    await markSeen(id, name, open.uid, seen)
    if (seen) void purge(cacheRules())
    open.seen = seen
    open.flags = seen ? [...open.flags, '\\Seen'] : open.flags.filter((flag) => flag !== '\\Seen')
    const row = messages.value.find((item) => item.uid === open.uid)
    if (row) row.seen = seen
    countUnseen(name, seen ? -1 : 1)
  }

  /** Moves the open mail to another folder of the account and opens the next one, or goes back to the list. */
  async function moveTo(target: string): Promise<void> {
    const id = accountId.value
    const name = folder.value
    const open = detail.value
    if (id === null || name === null || open === null || target === name) return
    try {
      await moveMessage(id, name, open.uid, target)
      setOnline(true)
    } catch (caught) {
      if (!isNetworkError(caught)) {
        fail('Could not move the mail', caught)
        return
      }
      setOnline(false)
      await enqueue({
        kind: 'move',
        accountId: id,
        folder: name,
        uid: open.uid,
        add: [],
        remove: [],
        target,
      })
    }
    await removeMail(id, name, open.uid)
    const index = messages.value.findIndex((item) => item.uid === open.uid)
    const next = messages.value[index + 1] ?? messages.value[index - 1]
    messages.value = messages.value.filter((item) => item.uid !== open.uid)
    total.value = Math.max(0, total.value - 1)
    const source = folders.value.find((item) => item.name === name)
    const destination = folders.value.find((item) => item.name === target)
    if (source && source.messages !== null) source.messages -= 1
    if (destination && destination.messages !== null) destination.messages += 1
    if (!open.seen) {
      countUnseen(name, -1)
      countUnseen(target, 1)
    }
    if (next) {
      await openMessage(next.uid)
    } else {
      selectedUid.value = null
      detail.value = null
      events.value = []
      pane.value = 'list'
    }
  }

  async function loadEvents(id: string, name: string, uid: number): Promise<void> {
    const ticket = ++eventsTicket
    eventsOffline.value = !isOnline.value
    if (eventsOffline.value) {
      events.value = []
      return
    }
    try {
      const found = await listEvents(id, name, uid)
      if (ticket === eventsTicket) events.value = found
    } catch (caught) {
      if (ticket !== eventsTicket) return
      events.value = []
      if (isNetworkError(caught)) {
        setOnline(false)
        eventsOffline.value = true
      }
      if (caught instanceof ApiError && caught.status === 401) onUnauthorized()
    }
  }

  /** Brings the browser to a place from the URL (deep link, back button); parts already shown are kept. */
  async function goTo(place: Place): Promise<void> {
    const id = place.accountId
    if (id === null || !accounts.value.some((item) => item.id === id)) return
    if (id !== accountId.value) {
      restore = { ...place, accountId: id }
      await selectAccount(id, true)
    } else if (place.folder !== null && place.folder !== folder.value) {
      await selectFolder(place.folder, place.uid)
    } else if (place.uid === null) {
      if (selectedUid.value === null) return
      selectedUid.value = null
      detail.value = null
      events.value = []
      pane.value = 'list'
    } else if (place.uid !== selectedUid.value) {
      await openMessage(place.uid)
    }
  }

  /** The back button of the narrow layout. */
  function back(): void {
    if (pane.value === 'message') pane.value = 'list'
    else if (pane.value === 'list') pane.value = 'folders'
  }

  return {
    accounts,
    accountId,
    folders,
    folder,
    currentFolder,
    messages,
    total,
    hasMore,
    detail,
    events,
    selectedUid,
    error,
    loading,
    foldersLoading,
    pane,
    panelOpen,
    active,
    actionsEnabled,
    context,
    fillDetached,
    fillContext,
    loadAccounts,
    refreshAccounts,
    selectAccount,
    selectFolder,
    loadMore,
    reloadFolders,
    reloadMessages,
    openMessage,
    allow,
    bodyOptions,
    setSeen,
    moveTo,
    isOnline,
    eventsOffline,
    queued,
    queueNotice,
    sendQueue,
    startOffline,
    stopOffline,
    goTo,
    back,
    clear,
    setUnauthorizedHandler,
  }
}
