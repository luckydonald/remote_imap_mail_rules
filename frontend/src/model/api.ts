/** Client of the server's editor endpoints. Without a server everything fails softly and the editor stays file based. */

const BASE = '/api/editor'

export interface EditorConfig {
  mode: 'server'
  source: 'file' | 'database'
  file_name: string | null
  exists: boolean
}

export class SaveError extends Error {
  readonly messages: string[]

  constructor(messages: string[]) {
    super(messages.join('; '))
    this.messages = messages
  }
}

/** The server's config, `'login'` when a server answers but wants a login (or cannot offer one), `null` when no server answers. */
export async function fetchConfig(): Promise<EditorConfig | 'login' | null> {
  try {
    const response = await fetch(`${BASE}/config`)
    if (response.status === 401 || response.status === 503) return 'login'
    if (!response.ok) return null
    const data: unknown = await response.json()
    if (typeof data !== 'object' || data === null || (data as { mode?: unknown }).mode !== 'server')
      return null
    return data as EditorConfig
  } catch {
    return null
  }
}

/** The YAML text of the server's rules file, `null` when it does not exist yet. */
export async function fetchRules(): Promise<string | null> {
  const response = await fetch(`${BASE}/rules`)
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`The server answered ${response.status}.`)
  return await response.text()
}

/** Writes the YAML to the server's rules file; throws `SaveError` with the server's messages when it is rejected. */
export async function saveRules(text: string): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE}/rules`, {
      method: 'PUT',
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      body: text,
    })
  } catch (error) {
    throw new SaveError([error instanceof Error ? error.message : String(error)])
  }
  if (response.ok) return
  let messages = [`The server answered ${response.status}.`]
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (Array.isArray(body.detail)) messages = body.detail.map(String)
    else if (typeof body.detail === 'string') messages = [body.detail]
  } catch {
    // keep the status message
  }
  throw new SaveError(messages)
}
