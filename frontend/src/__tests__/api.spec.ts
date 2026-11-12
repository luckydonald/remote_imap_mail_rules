import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchConfig, fetchRules, saveRules, SaveError } from '@/model/api'

const reply = (body: string, status = 200): Response =>
  new Response(status === 204 ? null : body, { status })

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('api', () => {
  it('reads the config of a server', async () => {
    const config = { mode: 'server', file_name: 'rules.yml', exists: true }
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply(JSON.stringify(config))))
    expect(await fetchConfig()).toEqual(config)
  })

  it('has no config without a server', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    expect(await fetchConfig()).toBeNull()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('<html>', 200)))
    expect(await fetchConfig()).toBeNull()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('', 502)))
    expect(await fetchConfig()).toBeNull()
  })

  it('starts from the config of the last visit when the network fails', async () => {
    const config = { mode: 'server', source: 'database', file_name: null, exists: true }
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply(JSON.stringify(config))))
    await fetchConfig()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    expect(await fetchConfig()).toEqual({ ...config, offline: true })
    // An answer of the server, even a failing one, is not offline.
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('', 502)))
    expect(await fetchConfig()).toBeNull()
  })

  it('fetches the rules, null while the file is missing', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('rules: []\n')))
    expect(await fetchRules()).toBe('rules: []\n')
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('{}', 404)))
    expect(await fetchRules()).toBeNull()
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply('', 500)))
    await expect(fetchRules()).rejects.toThrow('500')
  })

  it('puts the text as plain text', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(reply('', 204))
    vi.stubGlobal('fetch', fetchMock)
    await saveRules('rules: []\n')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/editor/rules',
      expect.objectContaining({ method: 'PUT', body: 'rules: []\n' }),
    )
  })

  it('throws the messages of a rejected save', async () => {
    const detail = ['rules.0.locations: Field required']
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(reply(JSON.stringify({ detail }), 422)),
    )
    const error = await saveRules('x').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(SaveError)
    expect((error as SaveError).messages).toEqual(detail)
  })
})
