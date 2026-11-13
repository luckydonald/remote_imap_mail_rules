/** Client of the server's stats, `GET /api/stats`. */

import { failure } from './http'

export interface Stats {
  database: {
    dialect: string
    /** The SQLite file with its write-ahead log, `null` for other databases. */
    size_bytes: number | null
  }
  tables: {
    accounts: number
    rules: number
    templates: number
    mcp_tokens: number
    mail_events: number
    mail_events_by_kind: Record<string, number>
  }
  first_event: string | null
  last_event: string | null
  data_dir_bytes: number
  watcher: {
    enabled: boolean
    actions_enabled: boolean
    /** Folders the watcher has scheduled or waits on, empty until its first check after a start. */
    folders: number
    jobs: number
  }
  started_at: string
  release: string
}

export async function fetchStats(): Promise<Stats> {
  const response = await fetch('/api/stats')
  if (!response.ok) throw await failure(response)
  return (await response.json()) as Stats
}
