/** Client of the server's login and read-only mail endpoints. */

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
  url: string
}

export interface Detail extends Summary {
  to: Address[]
  cc: Address[]
  reply_to: Address[]
  message_id: string | null
  text: string | null
  html: string | null
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

export async function getMessage(accountId: string, folder: string, uid: number): Promise<Detail> {
  const query = new URLSearchParams({ folder })
  return json<Detail>(await fetch(`${MAIL}/accounts/${accountId}/messages/${uid}?${query}`))
}

export { ApiError }
