import { isVar, type Expression, type RuleFile } from './types'
import { usableTemplates } from './validate'

export type TemplateHint = {
  template: string
  path: number[]
  variables: Record<string, unknown>
} & ({ rule: number } | { templateName: string })

/** Compare YAML values structurally. Only the pattern can bind variables. */
function matches(pattern: unknown, value: unknown, bindings?: Map<string, unknown>): boolean {
  if (bindings && isVar(pattern)) {
    if (bindings.has(pattern.var)) return matches(bindings.get(pattern.var), value)
    bindings.set(pattern.var, value)
    return true
  }
  if (Object.is(pattern, value) && (!bindings || typeof pattern !== 'object' || pattern === null))
    return true
  if (Array.isArray(pattern) || Array.isArray(value))
    return (
      Array.isArray(pattern) &&
      Array.isArray(value) &&
      pattern.length === value.length &&
      pattern.every((item, index) => matches(item, value[index], bindings))
    )
  if (
    typeof pattern !== 'object' ||
    pattern === null ||
    typeof value !== 'object' ||
    value === null
  )
    return false
  const entries = Object.entries(pattern)
  const record = value as Record<string, unknown>
  return (
    entries.length === Object.keys(record).length &&
    entries.every(
      ([key, item]) =>
        Object.prototype.hasOwnProperty.call(record, key) && matches(item, record[key], bindings),
    )
  )
}

export function matchTemplate(
  content: Expression,
  candidate: Expression,
  defaults: Record<string, unknown>,
): Record<string, unknown> | null {
  const bindings = new Map<string, unknown>()
  if (!matches(content, candidate, bindings)) return null
  return Object.fromEntries(
    [...bindings].filter(
      ([key, value]) =>
        !Object.prototype.hasOwnProperty.call(defaults, key) || !matches(defaults[key], value),
    ),
  )
}

function childrenOf(node: Expression): Expression[] {
  if (node.type === 'not') return [node.condition]
  if ((node.type === 'all' || node.type === 'any') && Array.isArray(node.conditions))
    return node.conditions
  return []
}

export function conditionAt(
  root: Expression | undefined,
  path: readonly number[],
): Expression | undefined {
  return path.reduce<Expression | undefined>(
    (node, index) => (node ? childrenOf(node)[index] : undefined),
    root,
  )
}

/** Search parent first so a suggestion covers its whole subtree. */
export function findReplaceable(file: RuleFile): TemplateHint[] {
  const hints: TemplateHint[] = []
  const templates = Object.entries(file.templates).filter(([, def]) => {
    const content = def?.content
    if (!content) return false
    if (content.type === 'not' || content.type === 'all' || content.type === 'any') return true
    // The discriminator alone does not make a variable-only leaf specific enough to suggest.
    return Object.entries(content).some(([key, value]) => key !== 'type' && !isVar(value))
  })

  function scan(root: Expression, owner: { rule: number } | { templateName: string }): void {
    const usable =
      'templateName' in owner ? new Set(usableTemplates(file, owner.templateName)) : null
    const candidates = usable ? templates.filter(([name]) => usable.has(name)) : templates
    function visit(node: Expression, path: number[]): void {
      if (!node || node.type === 'template') return
      for (const [template, def] of candidates) {
        const variables = matchTemplate(def.content, node, def.defaults ?? {})
        if (variables !== null) {
          hints.push({ ...owner, template, path, variables })
          return
        }
      }
      childrenOf(node).forEach((child, index) => visit(child, [...path, index]))
    }
    visit(root, [])
  }

  if (Array.isArray(file.rules))
    file.rules.forEach((rule, index) => scan(rule?.when, { rule: index }))
  for (const [templateName, def] of Object.entries(file.templates))
    scan(def?.content, { templateName })
  return hints
}
