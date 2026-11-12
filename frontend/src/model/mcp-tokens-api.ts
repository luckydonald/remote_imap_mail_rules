/** Client of the server's MCP token endpoints (`/api/mcp-tokens`). */

import { failure } from './http'

const BASE = '/api/mcp-tokens'

export interface McpToken {
  id: string
  name: string
  prefix: string
  scopes: string[]
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

/** Only the answer to the creation has the plain token, it is never shown again. */
export interface CreatedMcpToken extends McpToken {
  token: string
}

export interface McpScopes {
  scopes: string[]
  presets: Record<string, string[]>
}

export async function fetchMcpTokens(): Promise<McpToken[]> {
  const response = await fetch(BASE)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as McpToken[]
}

export async function fetchMcpScopes(): Promise<McpScopes> {
  const response = await fetch(`${BASE}/scopes`)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as McpScopes
}

export async function createMcpToken(name: string, scopes: string[]): Promise<CreatedMcpToken> {
  const response = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, scopes }),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as CreatedMcpToken
}

export async function revokeMcpToken(id: string): Promise<void> {
  const response = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!response.ok) throw await failure(response)
}

/** The scopes grouped by resource, in the server's order: `accounts.password:r` and `:w` are the resource `accounts.password`. */
export function groupScopes(scopes: string[]): { resource: string; scopes: string[] }[] {
  const groups = new Map<string, string[]>()
  for (const scope of scopes) {
    const resource = scope.slice(0, scope.lastIndexOf(':'))
    groups.set(resource, [...(groups.get(resource) ?? []), scope])
  }
  return [...groups].map(([resource, list]) => ({ resource, scopes: list }))
}

export function scopeLetter(scope: string): string {
  return { r: 'read', w: 'write', d: 'delete' }[scope.slice(scope.lastIndexOf(':') + 1)] ?? scope
}
