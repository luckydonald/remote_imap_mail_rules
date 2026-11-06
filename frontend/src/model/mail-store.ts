/** State of the mail browser: accounts, folders, the paged message list and the open message. */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { listAccounts, type Account } from './accounts-api'
import type { MailContext } from './fill-from-mail'
import { ApiError, describeError } from './http'
import { usePrefsStore } from './prefs'
import {
  getMessage,
  listEvents,
  listFolders,
  listMessages,
  moveMessage,
  setFlags,
  type BodyOptions,
  type Detail,
  type Folder,
  type MailEvent,
  type Summary,
} from './mail-api'

/** On a narrow screen only one of the panes shows. */
export type Pane = 'folders' | 'list' | 'message'

const STORAGE_KEY = 'mail-browser'

/** Where the browser is: account, folder and open mail, each `null` while not chosen. */
export interface Place {
  accountId: string | null
  folder: string | null
  uid: number | null
}

/** What survives a reload: the place and the open mail, never credentials. */
interface Saved {
  accountId: string | null
  folder: string | null
  uid: number | null
  detail: Detail | null
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

export const useMailStore = defineStore('mail', () => {
  const prefs = usePrefsStore()
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
  const detail = ref<Detail | null>(restore?.detail ?? null)
  const selectedUid = ref<number | null>(restore?.uid ?? null)
  // The action log of the open mail; a failing log never hides the mail itself.
  const events = ref<MailEvent[]>([])
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
        detail: detail.value,
      })
    }
  })

  /** Forgets everything of the session, e.g. on log out. */
  function clear(): void {
    restore = null
    accounts.value = []
    accountId.value = null
    folders.value = []
    folder.value = null
    messages.value = []
    total.value = 0
    nextBefore.value = null
    detail.value = null
    events.value = []
    selectedUid.value = null
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
    if (target?.accountId) restore = { ...target, accountId: target.accountId, detail: null }
    try {
      accounts.value = await listAccounts()
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
      const found = await listFolders(id)
      if (accountId.value !== id) return
      folders.value = found.filter((item) => item.selectable)
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
      const page = await listMessages(id, name, before)
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
      remoteImages: prefs.remoteImages === 'allow',
      styles: prefs.mailStyles === 'allow',
    }
    void loadEvents(id, name, uid)
    try {
      const found = await getMessage(id, name, uid, bodyOptions.value)
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
      const found = await getMessage(id, name, uid, bodyOptions.value)
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
    try {
      const flag = '\\Seen'
      await setFlags(id, name, open.uid, seen ? { add: [flag] } : { remove: [flag] })
    } catch (caught) {
      fail('Could not change the mail', caught)
      return
    }
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
    } catch (caught) {
      fail('Could not move the mail', caught)
      return
    }
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
    try {
      const found = await listEvents(id, name, uid)
      if (ticket === eventsTicket) events.value = found
    } catch (caught) {
      if (ticket !== eventsTicket) return
      events.value = []
      if (caught instanceof ApiError && caught.status === 401) onUnauthorized()
    }
  }

  /** Brings the browser to a place from the URL (deep link, back button); parts already shown are kept. */
  async function goTo(place: Place): Promise<void> {
    const id = place.accountId
    if (id === null || !accounts.value.some((item) => item.id === id)) return
    if (id !== accountId.value) {
      restore = { ...place, accountId: id, detail: null }
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
    selectAccount,
    selectFolder,
    loadMore,
    openMessage,
    allow,
    bodyOptions,
    setSeen,
    moveTo,
    goTo,
    back,
    clear,
    setUnauthorizedHandler,
  }
})

export type MailStore = ReturnType<typeof useMailStore>
