import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchConfig } from '@/model/api'
import { ApiError } from '@/model/http'
import { getMessage, listEvents, listFolders, listMessages, login } from '@/model/mail-api'

const reply = (body: unknown, status = 200): Response =>
  new Response(status === 204 ? null : JSON.stringify(body), { status })

afterEach(() => vi.unstubAllGlobals())

describe('mail api', () => {
  it('logs in with the credentials as JSON', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(reply(null, 204))
    vi.stubGlobal('fetch', fetchMock)
    await login('me', 'secret')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'me', password: 'secret' }),
      }),
    )
  })

  it('lists the action log of a mail with an encoded folder', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(reply([{ id: 'e', kind: 'first_seen', rule_name: null }]))
    vi.stubGlobal('fetch', fetchMock)
    const events = await listEvents('acc', 'Lists/a b', 7)
    expect(events).toHaveLength(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/mail/accounts/acc/messages/7/events?folder=Lists%2Fa+b',
    )
  })

  it('throws the server message of a failed login', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(reply({ detail: 'Wrong username or password.' }, 401)),
    )
    const error = await login('me', 'x').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).messages).toEqual(['Wrong username or password.'])
    expect((error as ApiError).status).toBe(401)
  })

  it('builds the message list query with the cursor and an encoded folder', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(() =>
        Promise.resolve(reply({ messages: [], total: 0, next_before_uid: null })),
      )
    vi.stubGlobal('fetch', fetchMock)
    await listMessages('acc', 'INBOX/a b', 42, 10)
    expect(fetchMock.mock.calls[0]![0]).toBe(
      '/api/mail/accounts/acc/messages?folder=INBOX%2Fa+b&limit=10&before_uid=42',
    )
    await listMessages('acc', 'INBOX', null)
    expect(fetchMock.mock.calls[1]![0]).toBe(
      '/api/mail/accounts/acc/messages?folder=INBOX&limit=50',
    )
  })

  it('reads folders and one message', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(reply([]))
    vi.stubGlobal('fetch', fetchMock)
    expect(await listFolders('acc')).toEqual([])
    fetchMock.mockResolvedValue(reply({ uid: 7 }))
    expect((await getMessage('acc', 'INBOX', 7)).uid).toBe(7)
    expect(fetchMock.mock.calls[1]![0]).toBe('/api/mail/accounts/acc/messages/7?folder=INBOX')
  })

  it('tells a login wall from a missing server', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply({ detail: 'x' }, 401)))
    expect(await fetchConfig()).toBe('login')
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(reply({ detail: 'x' }, 503)))
    expect(await fetchConfig()).toBe('login')
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    expect(await fetchConfig()).toBeNull()
  })
})
