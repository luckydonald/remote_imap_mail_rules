import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AccountError,
  checkAccount,
  createAccount,
  deleteAccount,
  listAccounts,
  updateAccount,
  type AccountInput,
} from '@/model/accounts-api'

const INPUT: AccountInput = {
  id: '',
  name: 'Work',
  host: 'imap.work.example',
  port: 993,
  ssl: true,
  username: 'me',
  password: '',
  page_size: 50,
  poll_interval: 60,
}

const json = (data: unknown, status = 200): Response =>
  new Response(status === 204 ? null : JSON.stringify(data), { status })

afterEach(() => vi.unstubAllGlobals())

describe('accounts api', () => {
  it('lists accounts', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(json([{ id: 'a' }])))
    expect(await listAccounts()).toEqual([{ id: 'a' }])
  })

  it('sends a password on create and omits an empty one on update', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => json({ id: 'a' }))
    vi.stubGlobal('fetch', fetchMock)
    await createAccount({ ...INPUT, password: 'secret' })
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string).password).toBe('secret')
    await updateAccount('a', INPUT)
    expect(fetchMock.mock.calls[1]![0]).toBe('/api/accounts/a')
    expect(JSON.parse(fetchMock.mock.calls[1]![1]!.body as string).password).toBeNull()
  })

  it('sends an id only when one is set', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => json({ id: 'a' }))
    vi.stubGlobal('fetch', fetchMock)
    await updateAccount('a', INPUT)
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string).id).toBeNull()
    await updateAccount('a', { ...INPUT, id: ' 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11 ' })
    expect(JSON.parse(fetchMock.mock.calls[1]![1]!.body as string).id).toBe(
      '6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11',
    )
  })

  it('turns the server detail into messages', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockImplementation(async () => json({ detail: ['Still used by the rule: A'] }, 409)),
    )
    await expect(deleteAccount('a')).rejects.toThrow(AccountError)
    await expect(deleteAccount('a')).rejects.toThrow('Still used by the rule: A')
    vi.stubGlobal(
      'fetch',
      vi
        .fn<typeof fetch>()
        .mockImplementation(async () =>
          json({ detail: [{ loc: ['body', 'port'], msg: 'too small' }] }, 422),
        ),
    )
    await expect(createAccount(INPUT)).rejects.toThrow('port: too small')
  })

  it('checks the login with the form values, an empty password stays out of the request', async () => {
    const result = { ok: false, kind: 'rejected', message: 'authentication failed' }
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => json(result))
    vi.stubGlobal('fetch', fetchMock)
    expect(await checkAccount({ ...INPUT, id: 'a' })).toEqual(result)
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/accounts/check')
    expect(fetchMock.mock.calls[0]![1]!.method).toBe('POST')
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body as string)).toMatchObject({
      id: 'a',
      password: null,
    })
  })
})
