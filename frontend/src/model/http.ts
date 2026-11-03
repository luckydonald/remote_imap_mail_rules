/** Shared by the clients of the authenticated server endpoints. */

export class ApiError extends Error {
  readonly messages: string[]
  readonly status: number

  constructor(messages: string[], status = 0) {
    super(messages.join('; '))
    this.messages = messages
    this.status = status
  }
}

/** Turns an unsuccessful response into an `ApiError`, reading FastAPI's `detail` (a string, a list of strings or validation errors). */
export async function failure(response: Response): Promise<ApiError> {
  let messages = [`The server answered ${response.status}.`]
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') messages = [body.detail]
    else if (Array.isArray(body.detail))
      messages = body.detail.map((item) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? `${((item as { loc?: unknown[] }).loc ?? []).slice(1).join('.')}: ${String((item as { msg: unknown }).msg)}`
          : String(item),
      )
  } catch {
    // keep the status message
  }
  return new ApiError(messages, response.status)
}

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
