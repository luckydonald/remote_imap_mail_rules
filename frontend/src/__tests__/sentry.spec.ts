import * as Sentry from '@sentry/vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp } from 'vue'
import { createAppRouter } from '@/router'
import { createMemoryHistory } from 'vue-router'
import { fetchSentryConfig, setUpSentry } from '@/sentry'

vi.mock('@sentry/vue', async (original) => ({
  ...(await original<typeof import('@sentry/vue')>()),
  init: vi.fn<typeof Sentry.init>(),
}))

const config = {
  dsn: 'http://k@bugsink.example.com/1',
  environment: 'production',
  release: 'abc',
  traces_sample_rate: 0,
}
const reply = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status })

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(Sentry.init).mockClear()
})

describe('sentry', () => {
  it('reads the config from the server', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply({ sentry: config })))
    expect(await fetchSentryConfig()).toEqual(config)
  })

  it.each([
    ['switched off', reply({ sentry: null })],
    ['no server', reply('<html>', 502)],
    ['nonsense', reply({ sentry: { dsn: '' } })],
  ])('has no config when %s', async (_name, response) => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response))
    expect(await fetchSentryConfig()).toBeNull()
  })

  it('has no config when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    expect(await fetchSentryConfig()).toBeNull()
  })

  it('stays inert without a config', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply({ sentry: null })))
    expect(await setUpSentry(createApp({}), createAppRouter(createMemoryHistory()))).toBe(false)
    expect(Sentry.init).not.toHaveBeenCalled()
  })

  it('starts with the config, tracing only when asked for', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply({ sentry: config })))
    expect(await setUpSentry(createApp({}), createAppRouter(createMemoryHistory()))).toBe(true)
    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: config.dsn,
        release: 'abc',
        environment: 'production',
        integrations: [],
      }),
    )
  })
})
