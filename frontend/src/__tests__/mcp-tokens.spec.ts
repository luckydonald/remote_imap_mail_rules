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
  /** The dialog is teleported to the body, so it is not inside the wrapper. */
  async function openDialog(wrapper: ReturnType<typeof mount>): Promise<void> {
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '+ New token')!
      .trigger('click')
  }
  async function clickBody(label: string): Promise<void> {
    const button = [...document.body.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === label,
    )!
    button.click()
    await flushPromises()
  }
  async function setInput(selector: string, value: string): Promise<void> {
    const input = document.body.querySelector(selector) as HTMLInputElement
    input.value = value
    input.dispatchEvent(new Event('input'))
    await flushPromises()
  }
  async function setChecked(selector: string): Promise<void> {
    const input = document.body.querySelector(selector) as HTMLInputElement
    input.click()
    await flushPromises()
  }

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
    const wrapper = mount(McpTokens, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('No tokens yet.')
    expect(document.body.querySelector('form')).toBeNull()
    await openDialog(wrapper)
    const create = document.body.querySelector('button[type=submit]')!
    expect(create.hasAttribute('disabled')).toBe(true)
    await setInput('input[type=text]', 'claude')
    await setChecked('input[value="rules:read"]')
    document.body.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()
    expect(document.body.querySelector('form')).toBeNull()
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
    wrapper.unmount()
  })

  it('closes the dialog on Cancel and clears the fields', async () => {
    vi.stubGlobal('fetch', server())
    const wrapper = mount(McpTokens, { attachTo: document.body })
    await flushPromises()
    await openDialog(wrapper)
    await setInput('input[type=text]', 'claude')
    await setChecked('input[value="rules:read"]')
    await clickBody('Cancel')
    expect(document.body.querySelector('form')).toBeNull()
    await openDialog(wrapper)
    expect((document.body.querySelector('input[type=text]') as HTMLInputElement).value).toBe('')
    expect(
      (document.body.querySelector('input[value="rules:read"]') as HTMLInputElement).checked,
    ).toBe(false)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(document.body.querySelector('form')).toBeNull()
    wrapper.unmount()
  })

  it('applies a preset', async () => {
    vi.stubGlobal('fetch', server())
    const wrapper = mount(McpTokens, { attachTo: document.body })
    await flushPromises()
    await openDialog(wrapper)
    await clickBody('Read only')
    const checked = (value: string) =>
      (document.body.querySelector(`input[value="${value}"]`) as HTMLInputElement).checked
    expect(checked('rules:read')).toBe(true)
    expect(checked('rules:write')).toBe(false)
    wrapper.unmount()
  })
})
