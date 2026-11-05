/** Client of the server's action log across all mails. */

import { failure } from './http'
import type { MailEvent } from './mail-api'

const BASE = '/api/log'

export type EventKind = MailEvent['kind']

export const EVENT_KINDS: { kind: EventKind; label: string }[] = [
  { kind: 'first_seen', label: 'First seen' },
  { kind: 'rule_match', label: 'Rule matches' },
  { kind: 'action', label: 'Rule actions' },
  { kind: 'user_action', label: 'Your actions' },
]

/** One entry with the key of its mail, so it can link to it. */
export interface LogEntry extends MailEvent {
  account_id: string
  folder: string
  uid: number
  message_id: string | null
}

export interface LogPage {
  items: LogEntry[]
  /** The cursor of the following page, `null` on the last one. */
  next: string | null
}

export interface LogStatus {
  watcher_enabled: boolean
  /** In memory on the server, `null` after its restart until the watching wakes up. */
  last_run: string | null
  /** The earliest planned poll, `null` when every folder waits for a server push or nothing is scheduled yet. */
  next_run: string | null
  /** Some folder waits for a server push (`IDLE`), so it also wakes up without a planned time. */
  push: boolean
  last_change: string | null
  last_action: string | null
}

/** What the filter bar edits; empty strings and lists mean no filter. `since` and `until` are `datetime-local` values. */
export interface LogFilters {
  q: string
  account_id: string
  folder: string
  rule: string
  kinds: EventKind[]
  since: string
  until: string
}

export const NO_FILTERS: LogFilters = {
  q: '',
  account_id: '',
  folder: '',
  rule: '',
  kinds: [],
  since: '',
  until: '',
}

/** A `datetime-local` value is in the browser's time zone, the server wants an instant. */
function instant(local: string): string | null {
  const date = new Date(local)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

/** The query string of a page; `before` is the cursor of the previous page. */
export function logQuery(filters: LogFilters, before: string | null, limit = 50): URLSearchParams {
  const query = new URLSearchParams({ limit: String(limit) })
  if (filters.q.trim() !== '') query.set('q', filters.q.trim())
  if (filters.account_id !== '') query.set('account_id', filters.account_id)
  if (filters.folder.trim() !== '') query.set('folder', filters.folder.trim())
  if (filters.rule.trim() !== '') query.set('rule', filters.rule.trim())
  for (const kind of filters.kinds) query.append('kind', kind)
  const since = filters.since === '' ? null : instant(filters.since)
  if (since !== null) query.set('since', since)
  const until = filters.until === '' ? null : instant(filters.until)
  if (until !== null) query.set('until', until)
  if (before !== null) query.set('before', before)
  return query
}

export async function fetchLog(filters: LogFilters, before: string | null): Promise<LogPage> {
  const response = await fetch(`${BASE}/events?${logQuery(filters, before)}`)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as LogPage
}

export async function fetchLogStatus(): Promise<LogStatus> {
  const response = await fetch(`${BASE}/status`)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as LogStatus
}

const KIND_NAMES = new Set<string>(EVENT_KINDS.map((item) => item.kind))

/** The filters a route query holds; unknown kinds are dropped. */
export function filtersOfQuery(query: Record<string, unknown>): LogFilters {
  const text = (value: unknown): string => (typeof value === 'string' ? value : '')
  const kinds = [query.kind]
    .flat()
    .filter((kind): kind is EventKind => KIND_NAMES.has(String(kind)))
  return {
    q: text(query.q),
    account_id: text(query.account),
    folder: text(query.folder),
    rule: text(query.rule),
    kinds,
    since: text(query.since),
    until: text(query.until),
  }
}

/** The route query of the filters, without the empty ones so the URL stays short. */
export function queryOfFilters(filters: LogFilters): Record<string, string | string[]> {
  const query: Record<string, string | string[]> = {}
  if (filters.q !== '') query.q = filters.q
  if (filters.account_id !== '') query.account = filters.account_id
  if (filters.folder !== '') query.folder = filters.folder
  if (filters.rule !== '') query.rule = filters.rule
  if (filters.kinds.length > 0) query.kind = filters.kinds
  if (filters.since !== '') query.since = filters.since
  if (filters.until !== '') query.until = filters.until
  return query
}
