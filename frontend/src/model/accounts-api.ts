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
}

/** What the form edits; an empty `password` keeps the stored one on update. */
export interface AccountInput {
  name: string
  host: string
  port: number
  ssl: boolean
  username: string
  password: string
  page_size: number
  poll_interval: number
}

export { ApiError as AccountError } from './http'

function body(input: AccountInput, update: boolean): string {
  const { password, ...rest } = input
  return JSON.stringify({ ...rest, password: update && password === '' ? null : password })
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
