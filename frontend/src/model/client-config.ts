interface ClientConfig {
  sentry?: unknown
  todo_overlay?: unknown
}

interface TodoOverlayConfig {
  url?: string
  token?: string
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

async function requestClientConfig(): Promise<ClientConfig | null> {
  try {
    const response = await fetch('/api/public/client-config', { cache: 'no-store' })
    if (!response.ok) return null
    const body: unknown = await response.json()
    return isObject(body) ? body : null
  } catch {
    return null
  }
}

let clientConfig: Promise<ClientConfig | null> | undefined

/** Both startup consumers use the same runtime configuration. */
export function fetchClientConfig(): Promise<ClientConfig | null> {
  return (clientConfig ??= requestClientConfig())
}

export async function fetchTodoOverlayConfig(): Promise<TodoOverlayConfig | null> {
  const config = (await fetchClientConfig())?.todo_overlay
  if (!isObject(config)) return null
  const { url, token } = config
  if (url != null && typeof url !== 'string') return null
  if (token != null && typeof token !== 'string') return null
  return { ...(url ? { url } : {}), ...(token ? { token } : {}) }
}
