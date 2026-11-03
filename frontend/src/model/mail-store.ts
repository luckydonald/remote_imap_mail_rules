/** State of the mail browser: accounts, folders, the paged message list and the open message. */

import { computed, ref } from 'vue'
import { listAccounts, type Account } from './accounts-api'
import { ApiError, describeError } from './http'
import {
  getMessage,
  listFolders,
  listMessages,
  type Detail,
  type Folder,
  type Summary,
} from './mail-api'

/** On a narrow screen only one of the panes shows. */
export type Pane = 'folders' | 'list' | 'message'

export function createMailStore(onUnauthorized: () => void = () => {}) {
  const accounts = ref<Account[]>([])
  const accountId = ref<string | null>(null)
  const folders = ref<Folder[]>([])
  const folder = ref<string | null>(null)
  const messages = ref<Summary[]>([])
  const total = ref(0)
  const nextBefore = ref<number | null>(null)
  const detail = ref<Detail | null>(null)
  const selectedUid = ref<number | null>(null)
  const error = ref('')
  const loading = ref(false)
  const pane = ref<Pane>('folders')
  // Answers of requests that were overtaken by a newer choice are dropped.
  let listTicket = 0
  let detailTicket = 0

  const hasMore = computed(() => nextBefore.value !== null)
  const currentFolder = computed(() => folders.value.find((item) => item.name === folder.value))

  function fail(prefix: string, caught: unknown): void {
    if (caught instanceof ApiError && caught.status === 401) {
      onUnauthorized()
      return
    }
    error.value = `${prefix}: ${describeError(caught)}`
  }

  async function loadAccounts(): Promise<void> {
    try {
      accounts.value = await listAccounts()
      if (accountId.value === null && accounts.value[0]) await selectAccount(accounts.value[0].id)
    } catch (caught) {
      fail('Could not load the accounts', caught)
    }
  }

  async function selectAccount(id: string): Promise<void> {
    accountId.value = id
    folders.value = []
    folder.value = null
    messages.value = []
    detail.value = null
    selectedUid.value = null
    error.value = ''
    pane.value = 'folders'
    try {
      const found = await listFolders(id)
      if (accountId.value !== id) return
      folders.value = found.filter((item) => item.selectable)
      const inbox = folders.value.find((item) => item.special_use === 'inbox')
      if (inbox) await selectFolder(inbox.name)
    } catch (caught) {
      fail('Could not load the folders', caught)
    }
  }

  async function selectFolder(name: string): Promise<void> {
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
    await loadMore()
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
    detail.value = null
    error.value = ''
    pane.value = 'message'
    try {
      const found = await getMessage(id, name, uid)
      if (ticket === detailTicket) detail.value = found
    } catch (caught) {
      if (ticket === detailTicket) fail('Could not load the message', caught)
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
    selectedUid,
    error,
    loading,
    pane,
    loadAccounts,
    selectAccount,
    selectFolder,
    loadMore,
    openMessage,
    back,
  }
}

export type MailStore = ReturnType<typeof createMailStore>
