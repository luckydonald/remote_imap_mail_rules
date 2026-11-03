import { afterEach, describe, expect, it, vi } from 'vitest'
import { describeLoggedAction, describeStep, dryRun, runNow } from '@/model/dry-run'
import { ApiError } from '@/model/http'
import { eventLabel } from '@/model/mail-format'
import type { MailEvent } from '@/model/mail-api'

const reply = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status })

afterEach(() => vi.unstubAllGlobals())

describe('describeStep', () => {
  it('words planned steps', () => {
    const step = (type: string, args: Record<string, unknown> = {}) => ({
      type,
      args,
      status: 'planned' as const,
      reason: null,
    })
    expect(describeStep(step('mark_read'))).toBe('mark as read')
    expect(describeStep(step('flag', { value: false }))).toBe('remove the flag')
    expect(describeStep(step('keyword', { keyword: 'Todo', value: true }))).toBe(
      'add the keyword "Todo"',
    )
    expect(describeStep(step('move', { folder: 'Archive' }))).toBe('move to Archive')
  })

  it('says why a step does nothing', () => {
    expect(describeStep({ type: 'mark_read', args: {}, status: 'noop', reason: 'already' })).toBe(
      'mark as read (already so)',
    )
    expect(
      describeStep({
        type: 'move',
        args: { folder: 'X' },
        status: 'skipped',
        reason: 'cross_account_not_supported',
      }),
    ).toBe('move to X (moving to another account is not supported yet)')
  })
})

describe('the action log', () => {
  const event = (detail: Record<string, unknown>): MailEvent => ({
    id: 'e',
    kind: 'action',
    rule_name: 'invoices',
    detail,
    created_at: '2026-11-03T10:00:00Z',
  })

  it('words done, failed and skipped actions', () => {
    expect(eventLabel(event({ type: 'move', status: 'done', folder: 'Archive' }))).toBe(
      'Moved to Archive by the rule "invoices"',
    )
    expect(describeLoggedAction({ type: 'move', status: 'error', folder: 'A', reason: 'no' })).toBe(
      'Failed to move to A: no',
    )
    expect(
      describeLoggedAction({ type: 'move', status: 'skipped', folder: 'A', reason: 'superseded' }),
    ).toBe('Skipped "move to A" (another move came first)')
  })
})

describe('dry run api', () => {
  it('posts the rule and the unsaved text', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(reply({ rule: 'r', summary: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await dryRun('r', 'rules: []')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/dry-run',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ rule: 'r', yaml: 'rules: []' }),
      }),
    )
  })

  it('reports that the server is not applying rules', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(reply({ detail: 'actions_disabled' }, 409)),
    )
    const error = await runNow('r').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(409)
  })
})
