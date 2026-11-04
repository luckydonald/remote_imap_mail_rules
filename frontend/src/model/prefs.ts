/** View settings of this browser: how mails are shown. Kept in localStorage, nothing here is sent to the server. */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type BodyMode = 'html' | 'text'
/** `block` and `allow` are for every mail; `rules` is reserved for the allow rules of the rule file. */
export type Policy = 'block' | 'allow'

const STORAGE_KEY = 'mail-prefs'

interface Saved {
  bodyMode: BodyMode
  remoteImages: Policy
  mailStyles: Policy
}

function readSaved(): Partial<Saved> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Partial<Saved>) : {}
  } catch {
    return {}
  }
}

export const usePrefsStore = defineStore('prefs', () => {
  const saved = readSaved()
  const bodyMode = ref<BodyMode>(saved.bodyMode === 'text' ? 'text' : 'html')
  const remoteImages = ref<Policy>(saved.remoteImages === 'allow' ? 'allow' : 'block')
  const mailStyles = ref<Policy>(saved.mailStyles === 'allow' ? 'allow' : 'block')

  watch([bodyMode, remoteImages, mailStyles], () => {
    try {
      const value: Saved = {
        bodyMode: bodyMode.value,
        remoteImages: remoteImages.value,
        mailStyles: mailStyles.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      // A blocked storage only means the settings are forgotten with the tab.
    }
  })

  return { bodyMode, remoteImages, mailStyles }
})
