/**
 * Fills the values of conditions from a mail, so a rule can start from an example.
 * The mapping mirrors `rules/extract.py`, so a filled condition matches the mail it came from.
 */

import {
  addressFields,
  boolFields,
  dateFields,
  newExpression,
  numberFields,
  textFields,
} from './catalog'
import type { Address, Detail } from './mail-api'
import { isVar } from './types'
import type {
  AddressCondition,
  Expression,
  HeaderCondition,
  TemplateDef,
  TemplateUse,
  TextCondition,
} from './types'

/** Which part of an address to match, the values of `AddressPart`. */
export type Granularity = 'full' | 'name' | 'address' | 'local_part' | 'domain'

export const granularities: { value: Granularity; label: string }[] = [
  { value: 'full', label: 'Name and email' },
  { value: 'address', label: 'Email' },
  { value: 'name', label: 'Name' },
  { value: 'local_part', label: 'Before the @' },
  { value: 'domain', label: 'Domain' },
]

/** The mail and the place it was found in. */
export interface MailContext {
  detail: Detail
  accountId: string
  folder: string
}

const SYSTEM_FLAGS = new Set([
  '\\seen',
  '\\answered',
  '\\flagged',
  '\\deleted',
  '\\draft',
  '\\recent',
])

/** The values of a header, in the order of the mail. */
export function headerValues(detail: Detail, name: string): string[] {
  const wanted = name.toLowerCase()
  return detail.headers.filter((header) => header.name.toLowerCase() === wanted).map((h) => h.value)
}

/** One part of an address, `null` when the address does not have it. Same cases as `split_address`. */
export function addressPart(address: Address, part: Granularity): string | null {
  const at = address.address.lastIndexOf('@')
  const local = at >= 0 ? address.address.slice(0, at) : ''
  const domain = at >= 0 ? address.address.slice(at + 1) : address.address
  const value = {
    full: address.name ? `${address.name} <${address.address}>` : address.address,
    name: address.name,
    address: address.address,
    local_part: local,
    domain,
  }[part]
  return value || null
}

function addressesOf(detail: Detail, field: string): Address[] {
  const found = {
    from: [detail.sender],
    sender: detail.sender_header,
    reply_to: detail.reply_to,
    return_path: detail.return_path,
    to: detail.to,
    cc: detail.cc,
    bcc: detail.bcc,
    recipients: [...detail.to, ...detail.cc, ...detail.bcc],
    delivered_to: detail.delivered_to,
  }[field as 'from']
  return (found ?? []).filter((item) => item.address)
}

function authResults(detail: Detail, method: string): string[] {
  const pattern = new RegExp(`\\b${method}=(\\w+)`, 'gi')
  return headerValues(detail, 'Authentication-Results').flatMap((value) =>
    [...value.matchAll(pattern)].map((match) => (match[1] ?? '').toLowerCase()),
  )
}

/** The values of a text field of the mail; empty when the mail does not have the field. */
export function textValues(ctx: MailContext, field: string): string[] {
  const { detail } = ctx
  const attachments = detail.attachments
  switch (field) {
    case 'account_id':
      return [ctx.accountId]
    case 'folder':
      return [ctx.folder]
    case 'mime_type':
      return detail.mime_type ? [detail.mime_type] : []
    case 'keywords':
      return detail.flags.filter((flag) => !SYSTEM_FLAGS.has(flag.toLowerCase()))
    case 'attachment_mime_type':
      return attachments.map((item) => item.mime_type)
    case 'attachment_filename':
      return attachments.flatMap((item) => (item.filename ? [item.filename] : []))
    case 'attachment_extension':
      return attachments.flatMap((item) => (item.extension ? [item.extension] : []))
    case 'auth_spf':
      return authResults(detail, 'spf')
    case 'auth_dkim':
      return authResults(detail, 'dkim')
    case 'auth_dmarc':
      return authResults(detail, 'dmarc')
    case 'subject':
      return headerValues(detail, 'Subject')
    case 'message_id':
      return headerValues(detail, 'Message-ID')
    case 'in_reply_to':
      return headerValues(detail, 'In-Reply-To')
    case 'references':
      return headerValues(detail, 'References')
    case 'list_id':
      return headerValues(detail, 'List-Id')
    case 'auto_submitted':
      return headerValues(detail, 'Auto-Submitted')
    case 'precedence':
      return headerValues(detail, 'Precedence')
    case 'importance':
      return headerValues(detail, 'Importance')
  }
  // The bodies are too long to be useful as an example.
  return []
}

const NUMBER = /-?\d+(?:\.\d+)?/

function spamScore(detail: Detail): number | null {
  for (const name of ['X-Spam-Score', 'X-Rspamd-Score', 'X-Spam-Status', 'X-Spam-Level']) {
    const value = headerValues(detail, name)[0]
    if (value === undefined) continue
    if (name === 'X-Spam-Level') {
      const stars = value.trim()
      if (stars && /^\*+$/.test(stars)) return stars.length
      continue
    }
    const match =
      name === 'X-Spam-Status'
        ? new RegExp(`score=(${NUMBER.source})`).exec(value)
        : new RegExp(`^\\s*(${NUMBER.source})`).exec(value)
    if (match?.[1]) return Number(match[1])
  }
  return null
}

function spamFlag(detail: Detail): boolean | null {
  const flag = headerValues(detail, 'X-Spam-Flag')[0]
  if (flag !== undefined) return ['yes', 'true', '1'].includes(flag.trim().toLowerCase())
  const status = headerValues(detail, 'X-Spam-Status')[0]
  return status === undefined ? null : status.trim().toLowerCase().startsWith('yes')
}

/** The values of a number field; empty when the mail does not have the field. */
export function numberValues(detail: Detail, field: string): number[] {
  switch (field) {
    case 'size':
      return detail.size === null ? [] : [detail.size]
    case 'uid':
      return [detail.uid]
    case 'modseq':
      return detail.modseq === null ? [] : [detail.modseq]
    case 'attachments_count':
      return [detail.attachments.length]
    case 'attachment_size':
      return detail.attachments.flatMap((item) => (item.size === null ? [] : [item.size]))
    case 'spam_score': {
      const score = spamScore(detail)
      return score === null ? [] : [score]
    }
  }
  return []
}

/** The values of a bool field; empty when the mail does not have the field. */
export function boolValues(detail: Detail, field: string): boolean[] {
  const flag = (name: string) => detail.flags.some((item) => item.toLowerCase() === name)
  switch (field) {
    case 'seen':
      return [flag('\\seen')]
    case 'flagged':
      return [flag('\\flagged')]
    case 'answered':
      return [flag('\\answered')]
    case 'draft':
      return [flag('\\draft')]
    case 'deleted':
      return [flag('\\deleted')]
    case 'spam_flag': {
      const value = spamFlag(detail)
      return value === null ? [] : [value]
    }
    case 'is_reply':
      return [
        headerValues(detail, 'In-Reply-To').length > 0 ||
          headerValues(detail, 'References').length > 0,
      ]
    case 'has_list_unsubscribe':
      return [headerValues(detail, 'List-Unsubscribe').length > 0]
    case 'attachment_inline':
      return detail.attachments.map((item) => item.inline)
  }
  return []
}

/** The text value for a condition: the whole list for the `in` operator, else the first value. */
function textValue(values: string[], operator: unknown): string | string[] | null {
  if (values.length === 0) return null
  return operator === 'in' ? values : (values[0] ?? null)
}

function fillText(
  expr: TextCondition | HeaderCondition,
  values: string[],
): TextCondition | HeaderCondition {
  const value = textValue(values, expr.operator)
  return value === null ? expr : { ...expr, value }
}

function fillAddress(
  expr: AddressCondition,
  ctx: MailContext,
  granularity: Granularity,
): AddressCondition {
  if (isVar(expr.field)) return expr
  const parts = addressesOf(ctx.detail, expr.field).flatMap((item) => {
    const value = addressPart(item, granularity)
    return value === null ? [] : [value]
  })
  const value = textValue(parts, expr.operator)
  return value === null ? expr : { ...expr, part: granularity, value }
}

const GRANULARITIES = new Set<string>(granularities.map((item) => item.value))

function partOf(node: AddressCondition): Granularity {
  return typeof node.part === 'string' && GRANULARITIES.has(node.part)
    ? (node.part as Granularity)
    : 'address'
}

/**
 * Returns the address condition with another field and / or part.
 * With a mail open the value follows when it was empty or is what the mail gave for the old field and part,
 * a value typed by hand is kept. Template variables and a mail without the new value leave the value as it was.
 */
export function changeAddress(
  node: AddressCondition,
  change: { field?: string; part?: string },
  ctx: MailContext | null,
): AddressCondition {
  const next: AddressCondition = { ...node, ...change }
  if (!ctx || isVar(node.field) || isVar(node.part) || isVar(node.value)) return next
  const empty = node.value === '' || (Array.isArray(node.value) && node.value.length === 0)
  const before = fillAddress(node, ctx, partOf(node)).value
  if (!empty && JSON.stringify(before) !== JSON.stringify(node.value)) return next
  return fillAddress(next, ctx, partOf(next))
}

/** The mail's time as an absolute value, naive and UTC like the rule file. */
function absoluteTime(iso: string): { relative: false; value: string } {
  return { relative: false, value: new Date(iso).toISOString().replace(/\.\d{3}Z$/, '') }
}

/**
 * Returns the condition with its value taken from the mail, or the same condition when the mail
 * does not have that field, the field is a template variable, or the condition is not a leaf.
 * `granularity` applies to address conditions.
 */
export function fillExpression(
  expr: Expression,
  ctx: MailContext,
  granularity: Granularity = 'address',
): Expression {
  const { detail } = ctx
  switch (expr.type) {
    case 'text':
      return isVar(expr.field) ? expr : fillText(expr, textValues(ctx, expr.field))
    case 'header':
      return isVar(expr.name) ? expr : fillText(expr, headerValues(detail, expr.name))
    case 'address':
      return fillAddress(expr, ctx, granularity)
    case 'number': {
      const value = isVar(expr.field) ? undefined : numberValues(detail, expr.field)[0]
      if (value === undefined) return expr
      return { ...expr, value: expr.operator === 'between' ? [value, value] : value }
    }
    case 'date': {
      if (isVar(expr.field)) return expr
      const iso = expr.field === 'date_received' ? detail.date : detail.date_sent
      if (!iso) return expr
      const time = absoluteTime(iso)
      return { ...expr, value: expr.operator === 'between' ? [time, time] : time }
    }
    case 'bool': {
      const value = isVar(expr.field) ? undefined : boolValues(detail, expr.field)[0]
      return value === undefined ? expr : { ...expr, value }
    }
    default:
      // Groups and template uses have no value of their own, presence has nothing to fill.
      return expr
  }
}

/**
 * A new condition on a field, filled from the mail.
 * Text and address use `equals` and numbers `eq`, so the condition matches the mail it came from.
 */
export function conditionFor(
  field: string,
  ctx: MailContext,
  granularity: Granularity = 'address',
): Expression | null {
  let base: Expression
  if (addressFields.includes(field)) {
    base = { ...newExpression('address'), field, operator: 'equals' } as Expression
  } else if (textFields.includes(field)) {
    base = { ...newExpression('text'), field, operator: 'equals' } as Expression
  } else if (numberFields.includes(field)) {
    base = { ...newExpression('number'), field, operator: 'eq' } as Expression
  } else if (dateFields.includes(field)) {
    base = { ...newExpression('date'), field, operator: 'gte' } as Expression
  } else if (boolFields.includes(field)) {
    base = { ...newExpression('bool'), field } as Expression
  } else {
    return null
  }
  const filled = fillExpression(base, ctx, granularity)
  return filled === base ? null : filled
}

/**
 * Adds a condition to a rule's `when`.
 * Without `path` it goes into a root `all`, else the rule and the new condition are wrapped in a new `all`.
 * With a `path` (child indexes from the root, `[]` is the root group itself, `not` has the single child 0) it goes into that group:
 * an `all` / `any` gets it appended, and a `not` gets its child wrapped in an `all` so it stays one condition.
 * A path that leads nowhere falls back to no path.
 */
export function appendCondition(
  when: Expression,
  added: Expression,
  path?: readonly number[],
): Expression {
  if (path === undefined) {
    if (when.type === 'all') return { ...when, conditions: [...when.conditions, added] }
    return { type: 'all', conditions: [when, added] }
  }
  const [step, ...rest] = path
  if (step === undefined) {
    if (when.type === 'all' || when.type === 'any')
      return { ...when, conditions: [...when.conditions, added] }
    if (when.type === 'not')
      return { ...when, condition: { type: 'all', conditions: [when.condition, added] } }
    return { type: 'all', conditions: [when, added] }
  }
  const child = when.type === 'all' || when.type === 'any' ? when.conditions[step] : undefined
  if ((when.type === 'all' || when.type === 'any') && child) {
    const conditions = [...when.conditions]
    conditions[step] = appendCondition(child, added, rest)
    return { ...when, conditions }
  }
  if (when.type === 'not' && step === 0)
    return { ...when, condition: appendCondition(when.condition, added, rest) }
  return appendCondition(when, added)
}

/** The leaves of a template's content, in order. */
function leavesOf(expr: Expression): Expression[] {
  if (expr.type === 'all' || expr.type === 'any') return expr.conditions.flatMap(leavesOf)
  if (expr.type === 'not') return leavesOf(expr.condition)
  return [expr]
}

/**
 * A use of a template with its variables filled from the mail.
 * A variable is filled from the leaf it is the `value` of, using that leaf's own (concrete) field, header name and address part.
 * The first leaf that yields a value wins; a variable that no leaf can fill is left out, so the template's default applies.
 */
export function templateUseFor(ref: string, def: TemplateDef, ctx: MailContext): TemplateUse {
  const variables: Record<string, unknown> = {}
  for (const leaf of leavesOf(def.content)) {
    if (leaf.type === 'template' || !('value' in leaf) || !isVar(leaf.value)) continue
    const name = leaf.value.var
    if (name in variables) continue
    const probe = { ...leaf, value: '' } as Expression
    const filled = fillExpression(probe, ctx, leaf.type === 'address' ? partOf(leaf) : undefined)
    if (filled === probe || !('value' in filled) || filled.value === '') continue
    variables[name] = filled.value
  }
  return { type: 'template', ref, variables }
}

/** The groups of a `when` a condition can be added to, with their path and depth, e.g. to show them as a tree. */
export function groupsOf(
  when: Expression,
  path: number[] = [],
): { path: number[]; type: 'all' | 'any' | 'not'; depth: number }[] {
  if (when.type !== 'all' && when.type !== 'any' && when.type !== 'not') return []
  const children = when.type === 'not' ? [when.condition] : when.conditions
  return [
    { path, type: when.type, depth: path.length },
    ...children.flatMap((child, index) => groupsOf(child, [...path, index])),
  ]
}

/** Header names to suggest for a `header` condition: those of the open mail first, then the common ones, each once. */
export function headerSuggestions(ctx: MailContext | null, common: readonly string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const name of [...(ctx?.detail.headers.map((header) => header.name) ?? []), ...common]) {
    if (seen.has(name.toLowerCase())) continue
    seen.add(name.toLowerCase())
    result.push(name)
  }
  return result
}
