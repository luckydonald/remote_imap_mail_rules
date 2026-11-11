/** Client of the server's account endpoints. */

import { failure } from './http'

const BASE = '/api/accounts'

export interface Account {
  id: string
  name: string
  host: string
  port: number
  ssl: boolean
  username: string
  page_size: number
  poll_interval: number
  has_password: boolean
  /** Fields that differ from the account in the server's environment. */
  env_differs: string[]
  /** When the username or password were last set; the login fields below restart then. */
  auth_updated_at: string
  auth_failed_at: string | null
  auth_fail_count: number
  auth_ok_at: string | null
  /** The server's answer to the last rejected login. */
  auth_last_error: string | null
  /** The last login was rejected and none worked since. */
  needs_check: boolean
}

/** What the form edits; an empty `password` keeps the stored one on update. */
export interface AccountInput {
  /** Empty generates one on create and keeps the current one on update. */
  id: string
  name: string
  host: string
  port: number
  ssl: boolean
  username: string
  password: string
  page_size: number
  poll_interval: number
}

/** The outcome of trying the login with the form's values; a failed login is a normal answer, not an error. */
export interface AccountCheckResult {
  ok: boolean
  kind: 'ok' | 'rejected' | 'unreachable' | 'timeout'
  message: string
}

export { ApiError as AccountError } from './http'

function body(input: AccountInput, update: boolean): string {
  const { password, id, ...rest } = input
  return JSON.stringify({
    ...rest,
    id: id.trim() === '' ? null : id.trim(),
    password: update && password === '' ? null : password,
  })
}

export async function listAccounts(): Promise<Account[]> {
  const response = await fetch(BASE)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as Account[]
}

export async function createAccount(input: AccountInput): Promise<Account> {
  const response = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body(input, false),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as Account
}

export async function updateAccount(id: string, input: AccountInput): Promise<Account> {
  const response = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body(input, true),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as Account
}

export async function deleteAccount(id: string): Promise<void> {
  const response = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!response.ok) throw await failure(response)
}

/** Tries the login with the form's values. An empty password uses the stored one of `input.id`; nothing is saved or noted on the account. */
export async function checkAccount(input: AccountInput): Promise<AccountCheckResult> {
  const response = await fetch(`${BASE}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body(input, true),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as AccountCheckResult
}
