import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { parseRules, stringifyRules } from '@/model/yaml-io'
import { validateRules } from '@/model/validate'

const read = (name: string) => readFileSync(resolve(process.cwd(), '../rules', name), 'utf-8')

describe.each(['example.yml', 'rules.example.yml'])('%s', (name) => {
  it('round trips', () => {
    const file = parseRules(read(name))
    const again = parseRules(stringifyRules(file))
    expect(again).toEqual(file)
  })

  it('is valid', () => {
    expect(validateRules(parseRules(read(name)))).toEqual([])
  })
})

describe('templates', () => {
  it('keeps uses as references and writes anchors, merges and !var', () => {
    const file = parseRules(read('rules.example.yml'))
    expect(Object.keys(file.templates)).toContain('anonaddy-forward')
    const text = stringifyRules(file)
    expect(text).toContain('&template-anonaddy-forward')
    expect(text).toContain('<<: *template-anonaddy-forward')
    expect(text).toContain('value: !var forward_address')
  })
})

describe('validation', () => {
  it('reports an unbound variable', () => {
    const file = parseRules(read('rules.example.yml'))
    const rule = JSON.stringify(file.rules)
    expect(rule).toContain('template')
    file.templates['anonaddy-forward']!.defaults = {}
    const problems = validateRules(file)
    expect(problems.some((problem) => problem.message.includes('without value'))).toBe(true)
  })

  it('reports a schema error', () => {
    const file = parseRules(
      'rules:\n  - name: x\n    locations: [{account_id: nope}]\n    when: {type: bool, field: seen}\n',
    )
    expect(validateRules(file).length).toBeGreaterThan(0)
  })
})
