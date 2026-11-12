/**
 * The one central store of the frontend, one `defineStore` for everything about rules and mails.
 * Its parts are plain functions in their own files that return refs and functions, spread in here:
 * `rules.ts` (the rule editor's document), `mail.ts` (the mail browser), `prefs.ts` (view settings), `clipboard.ts` (cut and paste of rule blocks) and `menu.ts` (the shared dropdown slot).
 * Components call `useStore()` directly, no provide/inject and no second store.
 */

import { defineStore } from 'pinia'
import { useAddToRule } from './add-to-rule'
import { useClipboard } from './clipboard'
import { useMail } from './mail'
import { useMenus } from './menu'
import { usePrefs } from './prefs'
import { useRules } from './rules'

export type { Pane, Place } from './mail'

export const useStore = defineStore('app', () => {
  const prefs = usePrefs()
  return {
    ...useRules(),
    ...useMail(prefs),
    ...prefs,
    ...useClipboard(prefs),
    ...useMenus(),
    ...useAddToRule(),
  }
})

export type Store = ReturnType<typeof useStore>
