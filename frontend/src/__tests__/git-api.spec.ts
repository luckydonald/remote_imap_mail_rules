import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/model/http'
import { fetchGitState, generateSshKey, runGitAction, saveGitSettings } from '@/model/git-api'

const json = (data: unknown, status = 200): Response =>
  new Response(JSON.stringify(data), { status })

afterEach(() => vi.unstubAllGlobals())

describe('git api', () => {
  it('reads the state', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json({ directory: '/data/rules' }))
    vi.stubGlobal('fetch', fetchMock)
    expect((await fetchGitState()).directory).toBe('/data/rules')
    expect(fetchMock).toHaveBeenCalledWith('/api/git')
  })

  it('sends the settings with the token', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json({ directory: 'x' }))
    vi.stubGlobal('fetch', fetchMock)
    await saveGitSettings({
      enabled: true,
      auto_commit: true,
      auto_push: false,
      remote_url: 'https://example.com/r.git',
      branch: 'main',
      auth_method: 'https',
      username: 'me',
      author_name: 'A',
      author_email: 'a@example.com',
      token: 's3cret',
    })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/git/settings')
    expect(init?.method).toBe('PUT')
    expect(JSON.parse(String(init?.body)).token).toBe('s3cret')
  })

  it('posts actions and the key request', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(() => Promise.resolve(json({ done: false, state: {} })))
    vi.stubGlobal('fetch', fetchMock)
    expect((await runGitAction('commit')).done).toBe(false)
    await generateSshKey()
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/git/commit',
      '/api/git/ssh-key',
    ])
  })

  it('raises the server message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(json({ detail: 'rejected' }, 502)),
    )
    await expect(runGitAction('push')).rejects.toMatchObject({
      messages: ['rejected'],
      status: 502,
    })
    await expect(runGitAction('push')).rejects.toBeInstanceOf(ApiError)
  })
})
