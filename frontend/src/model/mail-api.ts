/** Client of the server's login and mail endpoints; reading is read-only, `setFlags` and `moveMessage` write and need `ACTIONS_ENABLED`. */

import { ApiError, failure } from './http'

const AUTH = '/api/auth'
const MAIL = '/api/mail'

export interface Folder {
  name: string
  display_name: string
  delimiter: string | null
  special_use: string | null
  selectable: boolean
  messages: number | null
  unseen: number | null
}

export interface Address {
  name: string
  address: string
}

export interface Summary {
  uid: number
  sender: Address
  subject: string
  date: string | null
  seen: boolean
  flagged: boolean
  answered: boolean
  has_attachments: boolean
  size: number | null
}

export interface Attachment {
  part: string
  filename: string | null
  mime_type: string
  size: number | null
  inline: boolean
  content_id: string | null
  extension: string | null
  url: string
}

export interface Header {
  name: string
  value: string
}

export interface Detail extends Summary {
  to: Address[]
  cc: Address[]
  bcc: Address[]
  reply_to: Address[]
  sender_header: Address[]
  return_path: Address[]
  delivered_to: Address[]
  headers: Header[]
  flags: string[]
  keywords: string[]
  date_sent: string | null
  mime_type: string | null
  modseq: number | null
  message_id: string | null
  text: string | null
  html: string | null
  /** Remote image URLs left out of `html`, unless `remote_images_allowed`. */
  blocked_images: string[]
  /** `cid:` images without a part in the mail. */
  broken_embeds: string[]
  styles_blocked: boolean
  remote_images_allowed: boolean
  styles_allowed: boolean
  attachments: Attachment[]
}

export interface Page {
  messages: Summary[]
  total: number
  next_before_uid: number | null
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${AUTH}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw await failure(response)
}

export async function logout(): Promise<void> {
  await fetch(`${AUTH}/logout`, { method: 'POST' })
}

export async function listFolders(accountId: string): Promise<Folder[]> {
  return json<Folder[]>(await fetch(`${MAIL}/accounts/${accountId}/folders`))
}

export async function listMessages(
  accountId: string,
  folder: string,
  beforeUid: number | null,
  limit = 50,
): Promise<Page> {
  const query = new URLSearchParams({ folder, limit: String(limit) })
  if (beforeUid !== null) query.set('before_uid', String(beforeUid))
  return json<Page>(await fetch(`${MAIL}/accounts/${accountId}/messages?${query}`))
}

/** What the server may let the HTML load: remote images and its own CSS, both off unless asked for. */
export interface BodyOptions {
  remoteImages?: boolean
  styles?: boolean
}

export async function getMessage(
  accountId: string,
  folder: string,
  uid: number,
  options: BodyOptions = {},
): Promise<Detail> {
  const query = new URLSearchParams({ folder })
  if (options.remoteImages) query.set('remote_images', 'true')
  if (options.styles) query.set('styles', 'true')
  return json<Detail>(await fetch(`${MAIL}/accounts/${accountId}/messages/${uid}?${query}`))
}

/** Sets and clears `\\Seen`, `\\Flagged` or `\\Answered` on one mail. */
export async function setFlags(
  accountId: string,
  folder: string,
  uid: number,
  change: { add?: string[]; remove?: string[] },
): Promise<void> {
  const query = new URLSearchParams({ folder })
  const response = await fetch(`${MAIL}/accounts/${accountId}/messages/${uid}/flags?${query}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ add: change.add ?? [], remove: change.remove ?? [] }),
  })
  if (!response.ok) throw await failure(response)
}

/** Moves one mail to another folder of the same account. */
export async function moveMessage(
  accountId: string,
  folder: string,
  uid: number,
  target: string,
): Promise<void> {
  const query = new URLSearchParams({ folder })
  const response = await fetch(`${MAIL}/accounts/${accountId}/messages/${uid}/move?${query}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder: target }),
  })
  if (!response.ok) throw await failure(response)
}

/** One entry of the action log of a mail, written by the server's watcher. */
export interface MailEvent {
  id: string
  kind: 'first_seen' | 'rule_match' | 'action' | 'user_action'
  rule_name: string | null
  detail: Record<string, unknown>
  created_at: string
}

export async function listEvents(
  accountId: string,
  folder: string,
  uid: number,
): Promise<MailEvent[]> {
  const query = new URLSearchParams({ folder })
  return json<MailEvent[]>(
    await fetch(`${MAIL}/accounts/${accountId}/messages/${uid}/events?${query}`),
  )
}

export { ApiError }
