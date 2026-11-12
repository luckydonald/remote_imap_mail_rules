/** View settings of this browser: how mails are shown and whether the rule editor uses the real clipboard. Kept in localStorage, nothing here is sent to the server. Part of the central store (`index.ts`). */

import { ref, watch } from 'vue'
import { fetchSettings, saveSettings, type CacheSettings } from '../settings-api'

export type BodyMode = 'html' | 'text'
/** `block` and `allow` are for every mail; `rules` is reserved for the allow rules of the rule file. */
export type Policy = 'block' | 'allow'

/** Whether the rule editor uses the real clipboard for cut and paste. */
export type Toggle = 'on' | 'off'

const STORAGE_KEY = 'mail-prefs'

interface Saved {
  bodyMode: BodyMode
  remoteImages: Policy
  mailStyles: Policy
  copyCut: Toggle
  readPaste: Toggle
  cacheUnread: boolean
  cacheOpenedUnread: boolean
  cacheInbox: boolean
  cacheInboxCount: number
  cacheMaxAgeDays: number
}

function readSaved(): Partial<Saved> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Partial<Saved>) : {}
  } catch {
    return {}
  }
}

export function usePrefs() {
  const saved = readSaved()
  const bodyMode = ref<BodyMode>(saved.bodyMode === 'text' ? 'text' : 'html')
  const remoteImages = ref<Policy>(saved.remoteImages === 'allow' ? 'allow' : 'block')
  const mailStyles = ref<Policy>(saved.mailStyles === 'allow' ? 'allow' : 'block')

  /** Copy a cut rule block as YAML to the clipboard (can spam clipboard history managers). */
  const copyCut = ref<Toggle>(saved.copyCut === 'off' ? 'off' : 'on')
  /** Read the clipboard when pasting a rule block (can spam permission prompts). */
  const readPaste = ref<Toggle>(saved.readPaste === 'off' ? 'off' : 'on')

  // What the offline cache keeps (see `offline/cache.ts`).
  const cacheUnread = ref(saved.cacheUnread !== false)
  const cacheOpenedUnread = ref(saved.cacheOpenedUnread !== false)
  const cacheInbox = ref(saved.cacheInbox !== false)
  const cacheInboxCount = ref(
    Number.isInteger(saved.cacheInboxCount) && (saved.cacheInboxCount as number) >= 0
      ? (saved.cacheInboxCount as number)
      : 200,
  )

  const cacheMaxAgeDays = ref(
    Number.isInteger(saved.cacheMaxAgeDays) && (saved.cacheMaxAgeDays as number) >= 0
      ? (saved.cacheMaxAgeDays as number)
      : 30,
  )

  watch(
    [
      bodyMode,
      remoteImages,
      mailStyles,
      copyCut,
      readPaste,
      cacheUnread,
      cacheOpenedUnread,
      cacheInbox,
      cacheInboxCount,
    ],
    () => {
      try {
        const value: Saved = {
          bodyMode: bodyMode.value,
          remoteImages: remoteImages.value,
          mailStyles: mailStyles.value,
          copyCut: copyCut.value,
          readPaste: readPaste.value,
          cacheUnread: cacheUnread.value,
          cacheOpenedUnread: cacheOpenedUnread.value,
          cacheInbox: cacheInbox.value,
          cacheInboxCount: cacheInboxCount.value,
          cacheMaxAgeDays: cacheMaxAgeDays.value,
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
      } catch {
        // A blocked storage only means the settings are forgotten with the tab.
      }
    },
  )

  // The cache rules are the admin's settings on the server, so every browser has the same. The values above are the copy of the last
  // visit (also what an offline start uses); `loadServerSettings` replaces them with the server's and later changes are sent to it.
  let serverCache: string | null = null
  let sendTimer: ReturnType<typeof setTimeout> | null = null

  function cacheValues(): CacheSettings {
    return {
      cache_unread: cacheUnread.value,
      cache_opened_unread: cacheOpenedUnread.value,
      cache_inbox: cacheInbox.value,
      cache_inbox_count: cacheInboxCount.value,
      cache_max_age_days: cacheMaxAgeDays.value,
    }
  }

  const validNumber = (value: unknown): boolean => Number.isInteger(value) && (value as number) >= 0

  /** Takes the server's cache rules; failures (offline, logged out) keep the local copy. */
  async function loadServerSettings(): Promise<void> {
    try {
      const found = await fetchSettings()
      serverCache = JSON.stringify(found)
      cacheUnread.value = found.cache_unread
      cacheOpenedUnread.value = found.cache_opened_unread
      cacheInbox.value = found.cache_inbox
      cacheInboxCount.value = found.cache_inbox_count
      cacheMaxAgeDays.value = found.cache_max_age_days
    } catch {
      // Keep what the last visit left.
    }
  }

  watch([cacheUnread, cacheOpenedUnread, cacheInbox, cacheInboxCount, cacheMaxAgeDays], () => {
    // Nothing is sent before the server's values are in (they would overwrite them), nor while a number field is empty.
    if (
      serverCache === null ||
      !validNumber(cacheInboxCount.value) ||
      !validNumber(cacheMaxAgeDays.value)
    )
      return
    if (JSON.stringify(cacheValues()) === serverCache) return
    if (sendTimer !== null) clearTimeout(sendTimer)
    sendTimer = setTimeout(async () => {
      sendTimer = null
      const values = cacheValues()
      try {
        serverCache = JSON.stringify(await saveSettings(values))
      } catch {
        // Offline or refused: the next load takes the server's values again.
      }
    }, 500)
  })

  return {
    loadServerSettings,
    bodyMode,
    remoteImages,
    mailStyles,
    copyCut,
    readPaste,
    cacheUnread,
    cacheOpenedUnread,
    cacheInbox,
    cacheInboxCount,
    cacheMaxAgeDays,
  }
}
