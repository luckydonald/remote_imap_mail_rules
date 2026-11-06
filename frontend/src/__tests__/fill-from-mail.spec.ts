import { describe, expect, it } from 'vitest'
import {
  appendCondition,
  changeAddress,
  groupsOf,
  conditionFor,
  describeExpression,
  fillExpression,
  headerSuggestions,
  refillTemplateUse,
  templateUseFor,
  type MailContext,
} from '@/model/fill-from-mail'
import { newExpression } from '@/model/catalog'
import type { Detail } from '@/model/mail-api'
import type { AddressCondition, Expression, TemplateDef } from '@/model/types'

const detail: Detail = {
  uid: 7,
  sender: { name: 'Max Muster', address: 'max.muster@example.com' },
  subject: 'Hello',
  date: '2026-11-03T08:30:00Z',
  seen: true,
  flagged: false,
  answered: false,
  has_attachments: true,
  size: 1234,
  to: [
    { name: '', address: 'a@example.org' },
    { name: 'B', address: 'b@example.org' },
  ],
  cc: [],
  bcc: [],
  reply_to: [],
  sender_header: [],
  return_path: [],
  delivered_to: [],
  headers: [
    { name: 'Subject', value: 'Hello' },
    { name: 'List-Id', value: '<news.example.com>' },
    { name: 'X-Custom', value: 'one' },
    { name: 'x-custom', value: 'two' },
    { name: 'Authentication-Results', value: 'mx; spf=pass; dkim=PASS; dmarc=fail' },
    { name: 'X-Spam-Status', value: 'No, score=2.5 required=5' },
  ],
  flags: ['\\Seen', 'Work'],
  keywords: ['Work'],
  date_sent: '2026-11-03T08:00:00+01:00',
  mime_type: 'multipart/mixed',
  modseq: 9,
  message_id: '<id@x>',
  text: 'hi',
  html: null,
  blocked_images: [],
  broken_embeds: [],
  styles_blocked: false,
  remote_images_allowed: false,
  styles_allowed: false,
  attachments: [
    {
      part: '2',
      filename: 'Report.PDF',
      mime_type: 'application/pdf',
      size: 100,
      inline: false,
      content_id: null,
      extension: 'pdf',
      url: '/p',
    },
  ],
}
const ctx: MailContext = { detail, accountId: 'acc-1', folder: 'INBOX' }

function fill(expr: Expression, granularity?: Parameters<typeof fillExpression>[2]) {
  return fillExpression(expr, ctx, granularity)
}

describe('change an address condition', () => {
  const base = { ...newExpression('address'), value: 'max.muster@example.com' } as AddressCondition

  it('follows the new part while the value came from the mail', () => {
    expect(changeAddress(base, { part: 'name' }, ctx)).toMatchObject({
      part: 'name',
      value: 'Max Muster',
    })
    expect(changeAddress(base, { field: 'to' }, ctx)).toMatchObject({
      field: 'to',
      value: 'a@example.org',
    })
  })

  it('fills an empty value', () => {
    expect(changeAddress({ ...base, value: '' }, { part: 'domain' }, ctx)).toMatchObject({
      value: 'example.com',
    })
  })

  it('keeps a value typed by hand, without a mail, and when the mail lacks the value', () => {
    expect(changeAddress({ ...base, value: 'mine' }, { part: 'name' }, ctx).value).toBe('mine')
    expect(changeAddress(base, { part: 'name' }, null)).toMatchObject({
      part: 'name',
      value: 'max.muster@example.com',
    })
    expect(changeAddress(base, { field: 'cc' }, ctx).value).toBe('max.muster@example.com')
  })
})

describe('fill from mail', () => {
  it('fills address conditions by granularity', () => {
    const base = newExpression('address')
    expect(fill(base, 'full')).toMatchObject({
      part: 'full',
      value: 'Max Muster <max.muster@example.com>',
    })
    expect(fill(base, 'address')).toMatchObject({
      part: 'address',
      value: 'max.muster@example.com',
    })
    expect(fill(base, 'name')).toMatchObject({ part: 'name', value: 'Max Muster' })
    expect(fill(base, 'local_part')).toMatchObject({ value: 'max.muster' })
    expect(fill(base, 'domain')).toMatchObject({ value: 'example.com' })
  })

  it('takes every address for the in operator and the first one otherwise', () => {
    const to = { ...newExpression('address'), field: 'to' } as Expression
    expect(fill(to)).toMatchObject({ value: 'a@example.org' })
    expect(fill({ ...to, operator: 'in' } as Expression)).toMatchObject({
      value: ['a@example.org', 'b@example.org'],
    })
  })

  it('fills text, header, number, date and bool conditions', () => {
    expect(fill(newExpression('text'))).toMatchObject({ value: 'Hello' })
    expect(fill({ ...newExpression('text'), field: 'folder' } as Expression)).toMatchObject({
      value: 'INBOX',
    })
    expect(fill({ ...newExpression('text'), field: 'auth_dkim' } as Expression)).toMatchObject({
      value: 'pass',
    })
    expect(fill({ ...newExpression('text'), field: 'keywords' } as Expression)).toMatchObject({
      value: 'Work',
    })
    expect(fill({ ...newExpression('header'), name: 'X-CUSTOM' } as Expression)).toMatchObject({
      value: 'one',
    })
    expect(fill(newExpression('number'))).toMatchObject({ value: 1234 })
    expect(
      fill({ ...newExpression('number'), field: 'spam_score', operator: 'between' } as Expression),
    ).toMatchObject({ value: [2.5, 2.5] })
    expect(fill(newExpression('date'))).toMatchObject({
      value: { relative: false, value: '2026-11-03T08:30:00' },
    })
    expect(fill({ ...newExpression('date'), field: 'date_sent' } as Expression)).toMatchObject({
      value: { relative: false, value: '2026-11-03T07:00:00' },
    })
    expect(fill({ ...newExpression('bool'), field: 'flagged' } as Expression)).toMatchObject({
      value: false,
    })
  })

  it('leaves what the mail does not have, variables and groups alone', () => {
    const missing = { ...newExpression('text'), field: 'list_id' } as Expression
    expect(fill({ ...missing, field: 'importance' } as Expression)).toMatchObject({ value: '' })
    expect(fill({ ...newExpression('text'), field: { var: 'f' } } as Expression)).toMatchObject({
      value: '',
    })
    expect(fill({ ...newExpression('text'), field: 'body_text' } as Expression)).toMatchObject({
      value: '',
    })
    const group = newExpression('all')
    expect(fill(group)).toBe(group)
  })

  it('makes a new condition on a field, or none', () => {
    expect(conditionFor('from', ctx, 'domain')).toMatchObject({
      type: 'address',
      field: 'from',
      part: 'domain',
      operator: 'equals',
      value: 'example.com',
    })
    expect(conditionFor('list_id', ctx)).toMatchObject({
      type: 'text',
      value: '<news.example.com>',
    })
    expect(conditionFor('uid', ctx)).toMatchObject({ type: 'number', operator: 'eq', value: 7 })
    expect(conditionFor('importance', ctx)).toBeNull()
    expect(conditionFor('nope', ctx)).toBeNull()
  })

  it('appends to an all group or wraps the rule in a new one', () => {
    const added = newExpression('bool')
    const first = newExpression('text')
    expect(appendCondition({ type: 'all', conditions: [first] }, added)).toEqual({
      type: 'all',
      conditions: [first, added],
    })
    expect(appendCondition(first, added)).toEqual({ type: 'all', conditions: [first, added] })
  })

  it('appends into the group a path names', () => {
    const added = newExpression('bool')
    const leaf = newExpression('text')
    const when: Expression = {
      type: 'all',
      conditions: [leaf, { type: 'any', conditions: [leaf] }, { type: 'not', condition: leaf }],
    }
    expect(groupsOf(when).map((group) => [group.path, group.type])).toEqual([
      [[], 'all'],
      [[1], 'any'],
      [[2], 'not'],
    ])
    const inAny = appendCondition(when, added, [1]) as { conditions: Expression[] }
    expect(inAny.conditions[1]).toEqual({ type: 'any', conditions: [leaf, added] })
    const inNot = appendCondition(when, added, [2]) as { conditions: Expression[] }
    expect(inNot.conditions[2]).toEqual({
      type: 'not',
      condition: { type: 'all', conditions: [leaf, added] },
    })
    expect(appendCondition({ type: 'any', conditions: [leaf] }, added, [])).toEqual({
      type: 'any',
      conditions: [leaf, added],
    })
    expect(appendCondition(when, added, [9]).type).toBe('all')
  })

  it('inserts at an index of the group, clamped to it', () => {
    const added = newExpression('bool')
    const a = { ...newExpression('text'), value: 'a' } as Expression
    const b = { ...newExpression('text'), value: 'b' } as Expression
    const when: Expression = { type: 'all', conditions: [a, b] }
    const at = (index: number) =>
      (appendCondition(when, added, [], index) as { conditions: Expression[] }).conditions
    expect(at(0)).toEqual([added, a, b])
    expect(at(1)).toEqual([a, added, b])
    expect(at(2)).toEqual([a, b, added])
    expect(at(99)).toEqual([a, b, added])
    expect(at(-3)).toEqual([added, a, b])
    const nested: Expression = { type: 'all', conditions: [a, { type: 'any', conditions: [b] }] }
    const inner = appendCondition(nested, added, [1], 0) as { conditions: Expression[] }
    expect(inner.conditions[1]).toEqual({ type: 'any', conditions: [added, b] })
  })

  it('inserts before or after the child of a not, and around a lone condition', () => {
    const added = newExpression('bool')
    const leaf = newExpression('text')
    expect(appendCondition({ type: 'not', condition: leaf }, added, [], 0)).toEqual({
      type: 'not',
      condition: { type: 'all', conditions: [added, leaf] },
    })
    expect(appendCondition({ type: 'not', condition: leaf }, added, [], 1)).toEqual({
      type: 'not',
      condition: { type: 'all', conditions: [leaf, added] },
    })
    expect(appendCondition(leaf, added, [], 0)).toEqual({ type: 'all', conditions: [added, leaf] })
    expect(appendCondition(leaf, added, [], 1)).toEqual({ type: 'all', conditions: [leaf, added] })
  })
})

describe('headerSuggestions', () => {
  it('offers the headers of the open mail first, then the common ones, each once', () => {
    expect(headerSuggestions(ctx, ['list-id', 'X-Mailer'])).toEqual([
      'Subject',
      'List-Id',
      'X-Custom',
      'Authentication-Results',
      'X-Spam-Status',
      'X-Mailer',
    ])
  })

  it('offers only the common ones without an open mail', () => {
    expect(headerSuggestions(null, ['X-Mailer'])).toEqual(['X-Mailer'])
  })
})

describe('templateUseFor', () => {
  const def: TemplateDef = {
    type: 'template',
    defaults: { who: 'default' },
    content: {
      type: 'all',
      conditions: [
        {
          type: 'address',
          field: 'from',
          part: 'address',
          operator: 'equals',
          value: { var: 'addr' },
        },
        { type: 'address', field: 'from', part: 'name', operator: 'equals', value: { var: 'who' } },
        { type: 'text', field: 'subject', operator: 'equals', value: { var: 'addr' } },
        { type: 'text', field: { var: 'f' }, operator: 'equals', value: { var: 'other' } },
      ],
    },
  }

  it('fills each variable from the field and part of the leaf it sits in', () => {
    expect(templateUseFor('t', def, ctx)).toEqual({
      type: 'template',
      ref: 't',
      variables: { addr: 'max.muster@example.com', who: 'Max Muster' },
    })
  })

  it('leaves out a variable the mail cannot fill, so the default applies', () => {
    const noName = { ...ctx, detail: { ...detail, sender: { name: '', address: 'x@example.com' } } }
    expect(templateUseFor('t', def, noName).variables).toEqual({ addr: 'x@example.com' })
  })

  it('fills a new template use through fillExpression when the templates are given', () => {
    const use = newExpression('template', ['t'])
    expect(fillExpression(use, ctx, 'address', { t: def })).toEqual({
      type: 'template',
      ref: 't',
      variables: { addr: 'max.muster@example.com', who: 'Max Muster' },
    })
    expect(fillExpression(use, ctx)).toEqual(use)
  })

  it('refills with another template and drops the values of the old one', () => {
    const other: TemplateDef = {
      type: 'template',
      defaults: {},
      content: { type: 'text', field: 'subject', operator: 'equals', value: { var: 'subj' } },
    }
    const use = { type: 'template' as const, ref: 't', variables: { addr: 'typed' } }
    expect(refillTemplateUse(use, 'o', { t: def, o: other }, ctx)).toEqual({
      type: 'template',
      ref: 'o',
      variables: { subj: 'Hello' },
    })
  })

  it('only switches the ref without a mail or an unknown template', () => {
    const use = { type: 'template' as const, ref: 't', variables: { addr: 'typed' } }
    expect(refillTemplateUse(use, 'o', { t: def }, ctx).variables).toEqual({ addr: 'typed' })
    expect(refillTemplateUse(use, 't', { t: def }, null)).toEqual(use)
  })
})

describe('describeExpression', () => {
  it('reads each kind of condition as one line', () => {
    const text = { ...newExpression('text'), field: 'subject', operator: 'contains', value: 'hi' }
    expect(describeExpression(text as Expression)).toBe('subject contains "hi"')
    const address = {
      ...newExpression('address'),
      field: 'from',
      part: 'domain',
      operator: 'equals',
      value: 'example.com',
    }
    expect(describeExpression(address as Expression)).toBe('from.domain equals "example.com"')
    expect(describeExpression({ type: 'bool', field: 'seen' })).toBe('seen = true')
    expect(describeExpression({ type: 'bool', field: 'seen', value: false })).toBe('seen = false')
    expect(describeExpression({ type: 'presence', header: 'X-Foo' })).toBe('header X-Foo exists')
    expect(describeExpression({ type: 'presence', field: 'subject', value: false })).toBe(
      'subject is absent',
    )
    expect(
      describeExpression({ type: 'header', name: 'X-Foo', operator: 'equals', value: 'x' }),
    ).toBe('header X-Foo equals "x"')
    expect(describeExpression({ type: 'number', field: 'size', operator: 'gt', value: 5 })).toBe(
      'size gt 5',
    )
    expect(
      describeExpression({ type: 'template', ref: 'by-sender', variables: { sender: 'a@b.c' } }),
    ).toBe('template by-sender(sender = "a@b.c")')
    expect(describeExpression({ type: 'all', conditions: [text as Expression] })).toBe('all of 1')
    expect(describeExpression({ type: 'not', condition: text as Expression })).toBe('not')
  })

  it('shows a template variable as its name', () => {
    expect(
      describeExpression({
        type: 'text',
        field: 'subject',
        operator: 'equals',
        value: { var: 'who' },
      } as unknown as Expression),
    ).toBe('subject equals {who}')
  })
})
