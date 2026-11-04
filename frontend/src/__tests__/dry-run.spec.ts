import { afterEach, describe, expect, it, vi } from 'vitest'
import { describeLoggedAction, describeStep, dryRun, mergeSummary, runNow } from '@/model/dry-run'
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
        reason: 'superseded',
      }),
    ).toBe('move to X (another move came first)')
  })

  it('names a move to another account', () => {
    expect(
      describeStep({
        type: 'move',
        args: { folder: 'Inbox2', account_id: 'abc' },
        status: 'planned',
        reason: null,
      }),
    ).toBe('move to Inbox2 of another account')
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

  it('words the moves between accounts', () => {
    expect(
      eventLabel(event({ type: 'move', status: 'done', folder: 'In', account_id: 'abc' })),
    ).toBe('Moved to In of another account by the rule "invoices"')
    expect(
      eventLabel(
        event({
          type: 'moved_in',
          status: 'done',
          from: { account_id: 'abc', folder: 'INBOX', uid: 1 },
        }),
      ),
    ).toBe('Moved in from INBOX by the rule "invoices"')
    expect(
      describeLoggedAction({
        type: 'move',
        status: 'error',
        folder: 'A',
        reason: 'source_not_deleted',
      }),
    ).toBe('Failed to move to A: copied, but the original could not be deleted')
  })
})

describe('mergeSummary', () => {
  const row = (count: number, folder: string | null = null) => ({
    type: 'move',
    status: 'planned' as const,
    count,
    folder,
    keyword: null,
    reason: null,
  })

  it('adds up equal rows and keeps the biggest first', () => {
    const merged = mergeSummary([row(1, 'A'), row(5, 'B')], [row(2, 'A'), row(1, 'C')])
    expect(merged.map((item) => [item.folder, item.count])).toEqual([
      ['B', 5],
      ['A', 3],
      ['C', 1],
    ])
  })

  it('does not change its input', () => {
    const rows = [row(1, 'A')]
    mergeSummary(rows, [row(2, 'A')])
    expect(rows[0]?.count).toBe(1)
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

  it('passes the cursor of the next page on', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(reply({ rule: 'r', summary: [] }))
    vi.stubGlobal('fetch', fetchMock)
    const cursor = { account_id: 'a', folder: 'INBOX', before_uid: 7 }
    await dryRun('r', 'rules: []', cursor)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/dry-run',
      expect.objectContaining({ body: JSON.stringify({ rule: 'r', yaml: 'rules: []', cursor }) }),
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
