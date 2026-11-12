/** Whether the server can be reached, shared by everything that needs it. */

import { computed, ref } from 'vue'

const HEALTH = '/api/public/health'
const PROBE_MS = 5000

// `navigator.onLine` only knows about the network card, so the result of the real requests decides.
const online = ref(true)
let probe: ReturnType<typeof setInterval> | null = null
const listeners = new Set<() => void>()

/** Runs `listener` every time the connection comes back. */
export function onReconnect(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

async function probeOnce(): Promise<void> {
  try {
    await fetch(HEALTH)
    setOnline(true)
  } catch {
    // still offline
  }
}

/** A request got an answer (`true`) or failed on the network (`false`). */
export function setOnline(value: boolean): void {
  const was = online.value
  online.value = value
  if (value) {
    if (probe !== null) clearInterval(probe)
    probe = null
    if (!was) for (const listener of listeners) listener()
  } else if (probe === null) {
    probe = setInterval(() => void probeOnce(), PROBE_MS)
  }
}

/** A failed `fetch` is a `TypeError`; an `ApiError` is an answer of the server. */
export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => void probeOnce())
  window.addEventListener('offline', () => setOnline(false))
}

export function useOnline() {
  return { isOnline: computed(() => online.value) }
}
