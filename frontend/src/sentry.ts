/** Error reporting to Sentry or Bugsink. The DSN comes from the server at runtime, so one build serves every deployment. */
import * as Sentry from '@sentry/vue'
import type { App } from 'vue'
import type { Router } from 'vue-router'

export interface SentryClientConfig {
  dsn: string
  environment: string | null
  release: string
  traces_sample_rate: number
}

function isConfig(value: unknown): value is SentryClientConfig {
  if (typeof value !== 'object' || value === null) return false
  const config = value as Record<string, unknown>
  return (
    typeof config.dsn === 'string' &&
    config.dsn !== '' &&
    typeof config.release === 'string' &&
    typeof config.traces_sample_rate === 'number'
  )
}

/** The reporting config of the server, `null` when it is off, the server is missing or does not answer sensibly. */
export async function fetchSentryConfig(): Promise<SentryClientConfig | null> {
  try {
    const response = await fetch('/api/public/client-config')
    if (!response.ok) return null
    const body = (await response.json()) as { sentry?: unknown }
    return isConfig(body.sentry) ? body.sentry : null
  } catch {
    return null
  }
}

/** Starts the reporting; the tracing integration is only added when tracing is on. */
export function initSentry(app: App, router: Router, config: SentryClientConfig): void {
  Sentry.init({
    app,
    dsn: config.dsn,
    environment: config.environment ?? undefined,
    release: config.release,
    integrations:
      config.traces_sample_rate > 0 ? [Sentry.browserTracingIntegration({ router })] : [],
    tracesSampleRate: config.traces_sample_rate,
  })
}

/** Starts the reporting once the server answered; the app is already shown, so a slow or missing server delays nothing. */
export async function setUpSentry(app: App, router: Router): Promise<boolean> {
  const config = await fetchSentryConfig()
  if (config === null) return false
  initSentry(app, router, config)
  return true
}
