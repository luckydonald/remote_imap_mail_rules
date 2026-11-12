/**
 * Updates of the app itself. A new build means a new `sw.js` (the browser compares it byte for byte), which installs and then waits.
 * `updateAvailable` tells the screens, `applyUpdate` lets it take over and reloads the page. Nothing reloads by itself.
 * The browser only looks for a new worker on a page load, so a tab that stays open asks again every hour, when it becomes visible and when the network is back.
 */

import { ref } from 'vue'
import type { registerSW } from 'virtual:pwa-register'
import { useOnline } from './online'

export const CHECK_MS = 60 * 60 * 1000

export const updateAvailable = ref(false)
let apply: ((reload?: boolean) => Promise<void>) | null = null

export function setUpUpdates(register: typeof registerSW, intervalMs = CHECK_MS): void {
  const { isOnline } = useOnline()
  apply = register({
    immediate: true,
    onNeedRefresh() {
      updateAvailable.value = true
    },
    onRegisteredSW(_url, registration) {
      if (!registration) return
      // Offline there is nothing to find, and a failing check is no error.
      const check = (): void => {
        if (isOnline.value) void registration.update().catch(() => {})
      }
      setInterval(check, intervalMs)
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') check()
      })
      window.addEventListener('online', check)
    },
  })
}

/** Activates the waiting worker and reloads the page with the new build. */
export async function applyUpdate(): Promise<void> {
  await apply?.(true)
}
