import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { parseRules, parseRulesWithComments, stringifyRules } from '@/model/yaml-io'
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

describe('comments', () => {
  const source = `# yaml-language-server: $schema=../schemas/rules.schema.json
$schema: "../schemas/rules.schema.json"

rules:
  # The first rule.
  - name: First
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11 # the main account
    when:
      type: bool
      field: seen # already read

  # The second rule.
  - name: Second
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:
      type: bool
      field: flagged
`

  const roundTrip = (edit: (file: ReturnType<typeof parseRules>) => void = () => {}) => {
    const { file, comments } = parseRulesWithComments(source)
    edit(file)
    return stringifyRules(file, comments)
  }

  it('survives a round trip, with the header only once', () => {
    const text = roundTrip()
    expect(text).toContain('# The first rule.')
    expect(text).toContain('# The second rule.')
    expect(text).toContain('# the main account')
    expect(text).toContain('# already read')
    expect(text.match(/yaml-language-server/g)).toHaveLength(1)
    expect(parseRules(text)).toEqual(parseRules(source))
  })

  it('is lost without the collected comments', () => {
    const { file } = parseRulesWithComments(source)
    expect(stringifyRules(file)).not.toContain('The first rule')
  })

  it('survives editing a value', () => {
    const text = roundTrip((file) => {
      const when = file.rules[0]!.when
      if (when.type === 'bool') when.field = 'answered'
    })
    expect(text).toContain('field: answered # already read')
  })

  it('follows a rule that moved', () => {
    const text = roundTrip((file) => {
      file.rules.reverse()
    })
    expect(text.indexOf('# The second rule.')).toBeLessThan(text.indexOf('name: Second'))
    expect(text.indexOf('name: Second')).toBeLessThan(text.indexOf('# The first rule.'))
    expect(text.indexOf('# The first rule.')).toBeLessThan(text.indexOf('name: First'))
  })

  it('drops the comments of a removed rule only', () => {
    const text = roundTrip((file) => {
      file.rules.splice(0, 1)
    })
    expect(text).not.toContain('The first rule')
    expect(text).not.toContain('already read')
    expect(text).toContain('# The second rule.')
  })

  it('keeps the comments of the example files', () => {
    const { file, comments } = parseRulesWithComments(read('rules.example.yml'))
    const text = stringifyRules(file, comments)
    expect(text).toContain('# A mail forwarded by anonaddy')
    expect(text).toContain('# Used when a rule does not set the variable.')
    expect(parseRules(text)).toEqual(file)
  })
})
