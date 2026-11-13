/** Client of the admin's settings on the server (`/api/settings`), the same in every browser. */

import { failure } from './http'

const BASE = '/api/settings'

/** When the mail view marks a mail read by itself. */
export type AutoRead = 'off' | 'open' | 'scrolled'

/** The admin's settings: the offline cache rules and the automatic read. */
export interface UserSettings {
  cache_unread: boolean
  cache_opened_unread: boolean
  cache_inbox: boolean
  cache_inbox_count: number
  cache_max_age_days: number
  auto_read: AutoRead
}

export async function fetchSettings(): Promise<UserSettings> {
  const response = await fetch(BASE)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as UserSettings
}

export async function saveSettings(settings: UserSettings): Promise<UserSettings> {
  const response = await fetch(BASE, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as UserSettings
}
