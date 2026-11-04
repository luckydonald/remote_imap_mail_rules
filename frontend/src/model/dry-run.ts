/** Client of the dry run endpoints, and the wording of actions for the dry run and for the action log. */

import { failure } from './http'

const BASE = '/api/dry-run'

export interface Step {
  type: string
  status: 'planned' | 'done' | 'noop' | 'skipped' | 'error'
  reason: string | null
  args: Record<string, unknown>
}

export interface Round {
  rule: string
  steps: Step[]
}

export interface SummaryRow {
  type: string
  status: Step['status']
  count: number
  folder: string | null
  keyword: string | null
  reason: string | null
}

export interface AffectedMail {
  uid: number
  account_id: string
  folder: string
  subject: string
  sender: { name: string; address: string }
  date: string | null
  rounds: Round[]
  moved_to: string | null
}

/** Where the next page starts; opaque for the client, pass it back as it is. */
export interface DryRunCursor {
  account_id: string
  folder: string | null
  before_uid: number | null
}

/** One page of the dry run: the counts and mails are for the mails looked at in this page only. */
export interface DryRunPage {
  rule: string
  actions_enabled: boolean
  inspected: number
  affected: number
  summary: SummaryRow[]
  mails: AffectedMail[]
  errors: string[]
  next: DryRunCursor | null
}

/** Adds the counts of a page to the summary so far, rows with the same step are one row. */
export function mergeSummary(rows: SummaryRow[], more: SummaryRow[]): SummaryRow[] {
  const merged = rows.map((row) => ({ ...row }))
  for (const row of more) {
    const same = merged.find(
      (item) =>
        item.type === row.type &&
        item.status === row.status &&
        item.folder === row.folder &&
        item.keyword === row.keyword &&
        item.reason === row.reason,
    )
    if (same) same.count += row.count
    else merged.push({ ...row })
  }
  return merged.sort((a, b) => b.count - a.count)
}

export interface RunResult {
  applied: number
  steps: Record<string, number>
  errors: string[]
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

/** One page of what the rule would do. `yaml` is the editor's (maybe unsaved) text, nothing is written anywhere. */
export function dryRun(
  rule: string,
  yaml: string,
  cursor: DryRunCursor | null = null,
): Promise<DryRunPage> {
  return post('', cursor ? { rule, yaml, cursor } : { rule, yaml })
}

/** Applies the stored rule for real; the server refuses with 409 while it is not applying rules. */
export function runNow(rule: string): Promise<RunResult> {
  return post('/run', { rule })
}

interface Wording {
  plan: string
  past: string
}

function wording(type: string, args: Record<string, unknown>): Wording {
  const off = args.value === false
  const folder = String(args.folder ?? '?')
  const where = args.account_id ? `${folder} of another account` : folder
  const keyword = String(args.keyword ?? '?')
  switch (type) {
    case 'mark_read':
      return { plan: 'mark as read', past: 'Marked as read' }
    case 'mark_unread':
      return { plan: 'mark as unread', past: 'Marked as unread' }
    case 'flag':
      return off
        ? { plan: 'remove the flag', past: 'Removed the flag' }
        : { plan: 'flag', past: 'Flagged' }
    case 'keyword':
      return off
        ? { plan: `remove the keyword "${keyword}"`, past: `Removed the keyword "${keyword}"` }
        : { plan: `add the keyword "${keyword}"`, past: `Added the keyword "${keyword}"` }
    case 'move':
      return { plan: `move to ${where}`, past: `Moved to ${where}` }
    case 'moved_in': {
      const from = (args.from ?? {}) as Record<string, unknown>
      const source = `Moved in from ${String(from.folder ?? '?')}`
      return { plan: source, past: source }
    }
    default:
      return { plan: type, past: type }
  }
}

const REASONS: Record<string, string> = {
  already: 'already so',
  superseded: 'another move came first',
  unknown_account: 'the target account does not exist',
  source_not_deleted: 'copied, but the original could not be deleted',
  move_loop: 'moved too often already',
  gone: 'the mail is gone',
}

/** A step in the dry run, e.g. `move to Archive`, with the reason it does nothing in brackets. */
export function describeStep(step: Pick<Step, 'type' | 'args' | 'status' | 'reason'>): string {
  const text = wording(step.type, step.args).plan
  if (step.status === 'planned' || step.status === 'done') return text
  const reason = step.reason ? (REASONS[step.reason] ?? step.reason) : step.status
  return `${text} (${reason})`
}

/** An `action` entry of the log, e.g. `Moved to Archive`. */
export function describeLoggedAction(detail: Record<string, unknown>): string {
  const type = String(detail.type ?? 'action')
  const text = wording(type, detail).past
  if (detail.status === 'error') {
    const reason = String(detail.reason ?? 'error')
    return `Failed to ${wording(type, detail).plan}: ${REASONS[reason] ?? reason}`
  }
  if (detail.status === 'skipped') {
    const reason = String(detail.reason ?? 'skipped')
    return `Skipped "${wording(type, detail).plan}" (${REASONS[reason] ?? reason})`
  }
  return text
}
