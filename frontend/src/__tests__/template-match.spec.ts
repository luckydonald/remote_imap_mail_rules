import { describe, expect, it } from 'vitest'
import { findReplaceable, matchTemplate } from '@/model/template-match'
import type { Expression, RuleFile, TemplateDef } from '@/model/types'

const seen = { type: 'bool', field: 'seen' } satisfies Expression
const subject = (value: string | string[] | { var: string }): Expression => ({
  type: 'text',
  field: 'subject',
  operator: 'equals',
  value,
})
const all = (...conditions: Expression[]): Expression => ({ type: 'all', conditions })
const definition = (content: Expression): TemplateDef => ({
  type: 'template',
  defaults: {},
  content,
})
const use = (ref: string, variables: Record<string, unknown> = {}): Expression => ({
  type: 'template',
  ref,
  variables,
})

describe('matchTemplate', () => {
  it('matches fixed conditions exactly and keeps group order', () => {
    expect(matchTemplate(seen, { ...seen }, {})).toEqual({})
    expect(matchTemplate(seen, { ...seen, value: false }, {})).toBeNull()
    expect(matchTemplate(all(seen, subject('Hi')), all(subject('Hi'), seen), {})).toBeNull()
  })

  it('binds values, requiring deep equality for repeated variables', () => {
    const pattern = all(subject({ var: 'words' }), subject({ var: 'words' }))
    const hello = subject(['hello', 'world'])
    expect(matchTemplate(pattern, all(hello, subject(['hello', 'world'])), {})).toEqual({
      words: ['hello', 'world'],
    })
    expect(matchTemplate(pattern, all(hello, subject(['world', 'hello'])), {})).toBeNull()
  })

  it('omits a binding equal to its default', () => {
    expect(
      matchTemplate(subject({ var: 'words' }), subject(['hello']), { words: ['hello'] }),
    ).toEqual({})
  })

  it('binds variables inside a date value', () => {
    const pattern = {
      type: 'date',
      field: 'date_received',
      operator: 'lt',
      value: { relative: { var: 'kind' }, value: { var: 'cutoff' } },
    } satisfies Expression
    const value = { relative: true, value: '7d' }
    expect(matchTemplate(pattern, { ...pattern, value }, {})).toEqual({ kind: true, cutoff: '7d' })
  })

  it('matches nested uses by ref and binds their variables', () => {
    const pattern = all(use('inner', { value: { var: 'outer' }, fixed: { a: 1, b: 2 } }))
    const values = { fixed: { b: 2, a: 1 }, value: { relative: true, value: '7d' } }
    expect(matchTemplate(pattern, all(use('inner', values)), {})).toEqual({ outer: values.value })
    expect(matchTemplate(pattern, all(use('other', values)), {})).toBeNull()
  })
})

describe('findReplaceable', () => {
  it('prefers the largest subtree, skips existing uses, and records child paths', () => {
    const group = all(seen, subject('Hi'))
    const file: RuleFile = {
      templates: { read: definition(seen), message: definition(group) },
      rules: [
        { name: 'group', locations: [], when: group },
        { name: 'child', locations: [], when: { type: 'not', condition: seen } },
        { name: 'already using a template', locations: [], when: use('read') },
      ],
    }
    expect(findReplaceable(file)).toEqual([
      { rule: 0, path: [], template: 'message', variables: {} },
      { rule: 1, path: [0], template: 'read', variables: {} },
      { templateName: 'message', path: [0], template: 'read', variables: {} },
    ])
  })

  it('excludes self matches and templates that would lead to a cycle', () => {
    const branch = all(use('middle'))
    const file: RuleFile = {
      templates: {
        outer: definition(all(seen, branch)),
        middle: definition(use('outer')),
        branch: definition(branch),
      },
      rules: [],
    }
    expect(findReplaceable(file)).toEqual([])
  })

  it('skips a leaf made entirely of variables', () => {
    const file: RuleFile = {
      templates: { anyBool: definition({ type: 'bool', field: { var: 'field' } }) },
      rules: [{ name: 'rule', locations: [], when: seen }],
    }
    expect(findReplaceable(file)).toEqual([])
  })
})
