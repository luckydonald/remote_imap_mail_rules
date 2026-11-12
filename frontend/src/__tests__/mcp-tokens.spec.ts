import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import McpTokens from '@/components/McpTokens.vue'
import {
  createMcpToken,
  fetchMcpScopes,
  fetchMcpTokens,
  groupScopes,
  revokeMcpToken,
  scopeAction,
} from '@/model/mcp-tokens-api'

const json = (data: unknown, status = 200): Response =>
  new Response(JSON.stringify(data), { status })

afterEach(() => vi.unstubAllGlobals())

describe('mcp tokens api', () => {
  it('reads tokens and scopes', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => json([]))
    vi.stubGlobal('fetch', fetchMock)
    await fetchMcpTokens()
    await fetchMcpScopes()
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/mcp-tokens',
      '/api/mcp-tokens/scopes',
    ])
  })

  it('creates and revokes', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json({ token: 'rimr_x' }, 201))
    vi.stubGlobal('fetch', fetchMock)
    expect((await createMcpToken('claude', ['rules:read'])).token).toBe('rimr_x')
    const [, init] = fetchMock.mock.calls[0]!
    expect(JSON.parse(String(init?.body))).toEqual({ name: 'claude', scopes: ['rules:read'] })
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await revokeMcpToken('abc')
    expect(fetchMock.mock.calls[1]![0]).toBe('/api/mcp-tokens/abc')
    expect(fetchMock.mock.calls[1]![1]?.method).toBe('DELETE')
  })

  it('groups scopes by resource', () => {
    expect(groupScopes(['rules:read', 'rules:write', 'accounts.password:read'])).toEqual([
      { resource: 'rules', scopes: ['rules:read', 'rules:write'] },
      { resource: 'accounts.password', scopes: ['accounts.password:read'] },
    ])
    expect(scopeAction('events:delete')).toBe('delete')
  })
})

describe('McpTokens', () => {
  function server() {
    const tokens: Record<string, unknown>[] = []
    return vi.fn<typeof fetch>(async (url, init) => {
      if (url === '/api/mcp-tokens/scopes')
        return json({
          scopes: ['rules:read', 'rules:write'],
          presets: { read_only: ['rules:read'] },
        })
      if (url === '/api/mcp-tokens' && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as { name: string; scopes: string[] }
        const row = {
          id: '1',
          name: body.name,
          prefix: 'rimr_abc',
          scopes: body.scopes,
          created_at: '2026-11-12T10:00:00Z',
          last_used_at: null,
          revoked_at: null,
        }
        tokens.push(row)
        return json({ ...row, token: 'rimr_abcSECRET' }, 201)
      }
      if (init?.method === 'DELETE') {
        tokens[0]!.revoked_at = '2026-11-12T11:00:00Z'
        return new Response(null, { status: 204 })
      }
      return json(tokens)
    })
  }

  it('creates a token, shows it once and revokes it after a confirmation', async () => {
    vi.stubGlobal('fetch', server())
    const wrapper = mount(McpTokens)
    await flushPromises()
    expect(wrapper.text()).toContain('No tokens yet.')
    const create = wrapper.find('button[type=submit]')
    expect(create.attributes('disabled')).toBeDefined()
    await wrapper.find('input[type=text]').setValue('claude')
    await wrapper.find('input[value="rules:read"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('.token-value').text()).toBe('rimr_abcSECRET')
    expect(wrapper.text()).toContain('rimr_abc…')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Done')!
      .trigger('click')
    expect(wrapper.text()).not.toContain('rimr_abcSECRET')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Revoke')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Revoke for good')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('revoked')
  })

  it('applies a preset', async () => {
    vi.stubGlobal('fetch', server())
    const wrapper = mount(McpTokens)
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Read only')!
      .trigger('click')
    expect((wrapper.find('input[value="rules:read"]').element as HTMLInputElement).checked).toBe(
      true,
    )
    expect((wrapper.find('input[value="rules:write"]').element as HTMLInputElement).checked).toBe(
      false,
    )
  })
})
