/** Client of the admin's settings on the server (`/api/settings`), the same in every browser. */

import { failure } from './http'

const BASE = '/api/settings'

/** The offline cache rules. */
export interface CacheSettings {
  cache_unread: boolean
  cache_opened_unread: boolean
  cache_inbox: boolean
  cache_inbox_count: number
  cache_max_age_days: number
}

export async function fetchSettings(): Promise<CacheSettings> {
  const response = await fetch(BASE)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as CacheSettings
}

export async function saveSettings(settings: CacheSettings): Promise<CacheSettings> {
  const response = await fetch(BASE, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as CacheSettings
}
