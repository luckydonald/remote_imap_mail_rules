import {
  Document,
  Pair,
  Scalar,
  YAMLMap,
  isMap,
  isScalar,
  parseDocument,
  visit,
  type ScalarTag,
} from 'yaml'
import type { Expression, RuleFile, TemplateDef, TemplateUse } from './types'
import { isVar } from './types'

const DEFAULT_SCHEMA_PATH = '../schemas/rules.schema.json'

/** `!var name` is the shorthand for `{var: name}`. */
const varTag: ScalarTag = {
  tag: '!var',
  identify: () => false,
  resolve: (str: string) => ({ var: str }),
  stringify: (item) => String((item as Scalar).value),
}

export class RulesParseError extends Error {}

type Json = Record<string, unknown>

function isObject(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Replaces `<<: *anchor` merges with `{type: template, ref, variables}`, found by the identity of the aliased object. */
function replaceUses(node: unknown, templates: Record<string, unknown>): unknown {
  if (Array.isArray(node)) return node.map((item) => replaceUses(item, templates))
  if (!isObject(node)) return node
  const merged = node['<<']
  if (merged !== undefined) {
    const ref = Object.keys(templates).find((key) => templates[key] === merged)
    if (ref !== undefined) {
      const variables = replaceUses(node.variables ?? {}, templates) as Record<string, unknown>
      return { type: 'template', ref, variables } satisfies TemplateUse
    }
  }
  return Object.fromEntries(
    Object.entries(node).map(([key, value]) => [key, replaceUses(value, templates)]),
  )
}

export function parseRules(text: string): RuleFile {
  const doc = parseDocument(text, { customTags: [varTag], merge: false })
  if (doc.errors.length > 0)
    throw new RulesParseError(doc.errors.map((error) => error.message).join('\n'))
  const raw = doc.toJS() ?? {}
  if (!isObject(raw))
    throw new RulesParseError('The top level of a rules file needs to be a mapping with `rules`.')
  const rawTemplates = isObject(raw.templates) ? raw.templates : {}
  const templates = Object.fromEntries(
    Object.entries(rawTemplates).map(([name, def]) => [name, replaceUses(def, rawTemplates)]),
  ) as Record<string, TemplateDef>
  const rules = replaceUses(raw.rules ?? [], rawTemplates) as RuleFile['rules']
  const file: RuleFile = { templates, rules }
  if (typeof raw.$schema === 'string') file.$schema = raw.$schema
  return file
}

function anchorName(template: string): string {
  return `template-${template.replace(/[^A-Za-z0-9_-]/g, '-')}`
}

export function stringifyRules(file: RuleFile): string {
  const data: Json = {}
  if (file.$schema !== undefined) data.$schema = file.$schema
  if (Object.keys(file.templates).length > 0) data.templates = file.templates
  data.rules = file.rules
  // JSON round trip drops `undefined`.
  const doc = new Document(JSON.parse(JSON.stringify(data)), { customTags: [varTag] })
  if (file.$schema !== undefined)
    doc.commentBefore = ` yaml-language-server: $schema=${file.$schema || DEFAULT_SCHEMA_PATH}`

  const templatesNode = doc.get('templates', true)
  const anchors = new Map<string, YAMLMap>()
  if (isMap(templatesNode)) {
    for (const pair of templatesNode.items) {
      if (isScalar(pair.key) && isMap(pair.value)) {
        const name = String(pair.key.value)
        pair.value.anchor = anchorName(name)
        anchors.set(name, pair.value)
      }
    }
  }

  visit(doc, {
    Map(_key, node) {
      if (node.items.length === 1) {
        const [only] = node.items
        if (
          only &&
          isScalar(only.key) &&
          only.key.value === 'var' &&
          isScalar(only.value) &&
          typeof only.value.value === 'string'
        ) {
          const scalar = new Scalar(only.value.value)
          scalar.tag = '!var'
          return scalar
        }
      }
      const type = node.get('type')
      const ref = node.get('ref')
      if (type === 'template' && typeof ref === 'string') {
        const target = anchors.get(ref)
        const rest = node.items.filter(
          (pair) =>
            !(isScalar(pair.key) && (pair.key.value === 'type' || pair.key.value === 'ref')),
        )
        const variables = rest.find((pair) => isScalar(pair.key) && pair.key.value === 'variables')
        const empty = isMap(variables?.value) && variables.value.items.length === 0
        const items = rest.filter((pair) => !(empty && pair === variables))
        if (target)
          items.unshift(new Pair(new Scalar('<<'), doc.createAlias(target, anchorName(ref))))
        else items.unshift(new Pair(new Scalar('ref'), new Scalar(ref)))
        node.items = items
      }
      return undefined
    },
  })
  return doc.toString({ lineWidth: 0 })
}

/** The file as the backend schema sees it: template uses merged with their definition. */
export function expandRules(file: RuleFile): unknown {
  const expandExpression = (expression: Expression, seen: string[]): unknown => {
    if (expression.type === 'template') {
      const def = file.templates[expression.ref]
      if (!def || seen.includes(expression.ref)) return { type: 'template', ref: expression.ref }
      return {
        type: 'template',
        defaults: def.defaults,
        variables: expression.variables,
        content: expandExpression(def.content, [...seen, expression.ref]),
      }
    }
    return expression
  }
  const walk = (node: unknown, seen: string[]): unknown => {
    if (Array.isArray(node)) return node.map((item) => walk(item, seen))
    if (!isObject(node) || isVar(node)) return node
    if (node.type === 'template' && typeof node.ref === 'string')
      return walk(expandExpression(node as unknown as Expression, seen), seen)
    return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, walk(value, seen)]))
  }
  return {
    ...(file.$schema !== undefined ? { $schema: file.$schema } : {}),
    templates: Object.fromEntries(
      Object.entries(file.templates).map(([name, def]) => [name, walk(def, [name])]),
    ),
    rules: walk(file.rules, []),
  }
}
