/** View settings of this browser: how mails are shown. Kept in localStorage, nothing here is sent to the server. */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

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

  /** Copy a cut rule block as YAML to the clipboard (can spam clipboard history managers). */
  const copyCut = ref<Toggle>(saved.copyCut === 'off' ? 'off' : 'on')
  /** Read the clipboard when pasting a rule block (can spam permission prompts). */
  const readPaste = ref<Toggle>(saved.readPaste === 'off' ? 'off' : 'on')

  watch([bodyMode, remoteImages, mailStyles, copyCut, readPaste], () => {
    try {
      const value: Saved = {
        bodyMode: bodyMode.value,
        remoteImages: remoteImages.value,
        mailStyles: mailStyles.value,
        copyCut: copyCut.value,
        readPaste: readPaste.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      // A blocked storage only means the settings are forgotten with the tab.
    }
  })

  return { bodyMode, remoteImages, mailStyles, copyCut, readPaste }
})
