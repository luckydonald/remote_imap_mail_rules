/** Client of the server's git endpoints for the rules folder. */

import { failure } from './http'

const BASE = '/api/git'

export type AuthMethod = 'none' | 'https' | 'ssh'

export interface GitSettings {
  enabled: boolean
  auto_commit: boolean
  auto_push: boolean
  remote_url: string
  branch: string
  auth_method: AuthMethod
  username: string
  has_token: boolean
  author_name: string
  author_email: string
}

export interface GitStatus {
  git_available: boolean
  initialized: boolean
  branch: string | null
  changed: string[]
  has_upstream: boolean
  ahead: number
  behind: number
  last_commit: string | null
  remote_configured: boolean
}

export interface GitState {
  settings: GitSettings
  status: GitStatus
  public_key: string | null
  last_error: string | null
  directory: string
}

/** What the form saves; `token` `null` keeps the stored one, an empty string clears it. */
export type GitSettingsInput = Omit<GitSettings, 'has_token'> & { token: string | null }

export type GitAction = 'init' | 'commit' | 'push' | 'fetch'

export async function fetchGitState(): Promise<GitState> {
  const response = await fetch(BASE)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as GitState
}

export async function saveGitSettings(input: GitSettingsInput): Promise<GitState> {
  const response = await fetch(`${BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as GitState
}

/** Runs one action; `done` is false for a commit with nothing to commit. */
export async function runGitAction(action: GitAction): Promise<{ done: boolean; state: GitState }> {
  const response = await fetch(`${BASE}/${action}`, { method: 'POST' })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as { done: boolean; state: GitState }
}

export async function generateSshKey(): Promise<GitState> {
  const response = await fetch(`${BASE}/ssh-key`, { method: 'POST' })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as GitState
}
