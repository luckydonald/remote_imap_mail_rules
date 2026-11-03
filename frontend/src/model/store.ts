import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { validateRules } from './validate'
import { parseRulesWithComments, stringifyRules } from './yaml-io'
import type { CommentMap } from './comments'
import { newExpression } from './catalog'
import type { Rule, RuleFile } from './types'

export type View = { kind: 'rule'; index: number } | { kind: 'templates' } | { kind: 'yaml' }

const HISTORY_LIMIT = 100

export function emptyFile(): RuleFile {
  return { $schema: '../schemas/rules.schema.json', templates: {}, rules: [] }
}

export function newRule(): Rule {
  return {
    name: 'New rule',
    enabled: true,
    locations: [{ account_id: '', folder: 'INBOX', recursive: false }],
    when: newExpression('text'),
    actions: [],
  }
}

export function createStore(initial: RuleFile = emptyFile()) {
  const file = reactive<RuleFile>(initial)
  const view = ref<View>({ kind: 'yaml' })
  const fileName = ref('rules.yml')
  /** Comments of the loaded text, written back when generating the YAML. */
  const comments = shallowRef<CommentMap | undefined>()
  const past: string[] = []
  const future: string[] = []
  const canUndo = ref(false)
  const canRedo = ref(false)
  let last = JSON.stringify(file)
  let applying = false

  const sync = () => {
    canUndo.value = past.length > 0
    canRedo.value = future.length > 0
  }

  watch(
    () => JSON.stringify(file),
    (json) => {
      if (applying || json === last) return
      past.push(last)
      if (past.length > HISTORY_LIMIT) past.shift()
      future.length = 0
      last = json
      sync()
    },
    { flush: 'sync' },
  )

  function restore(json: string): void {
    applying = true
    const data = JSON.parse(json) as RuleFile
    file.$schema = data.$schema
    file.templates = data.templates
    file.rules = data.rules
    last = json
    applying = false
    const selected = view.value
    if (selected.kind === 'rule' && selected.index >= file.rules.length)
      view.value = { kind: 'yaml' }
    sync()
  }

  function undo(): void {
    const previous = past.pop()
    if (previous === undefined) return
    future.push(last)
    restore(previous)
  }

  function redo(): void {
    const next = future.pop()
    if (next === undefined) return
    past.push(last)
    restore(next)
  }

  /** Replaces the whole file, as one undo step. */
  function load(text: string, name?: string): void {
    const parsed = parseRulesWithComments(text)
    const data = parsed.file
    comments.value = parsed.comments
    file.$schema = data.$schema
    file.templates = data.templates
    file.rules = data.rules
    if (name) fileName.value = name
    view.value = file.rules.length > 0 ? { kind: 'rule', index: 0 } : { kind: 'yaml' }
  }

  const problems = computed(() => validateRules(file))
  const yaml = computed(() => stringifyRules(file, comments.value))

  function addRule(): void {
    file.rules.push(newRule())
    view.value = { kind: 'rule', index: file.rules.length - 1 }
  }

  function duplicateRule(index: number): void {
    const rule = file.rules[index]
    if (!rule) return
    const copy = JSON.parse(JSON.stringify(rule)) as Rule
    copy.name = `${rule.name} (copy)`
    file.rules.splice(index + 1, 0, copy)
    view.value = { kind: 'rule', index: index + 1 }
  }

  function removeRule(index: number): void {
    file.rules.splice(index, 1)
    view.value =
      file.rules.length > 0
        ? { kind: 'rule', index: Math.min(index, file.rules.length - 1) }
        : { kind: 'yaml' }
  }

  function moveRule(index: number, delta: -1 | 1): void {
    const target = index + delta
    if (target < 0 || target >= file.rules.length) return
    const [rule] = file.rules.splice(index, 1)
    if (rule) file.rules.splice(target, 0, rule)
    view.value = { kind: 'rule', index: target }
  }

  /** Rule indices and template names that use a template. */
  function usesOf(name: string): { rules: number[]; templates: string[] } {
    const hit = (node: unknown): boolean => {
      if (Array.isArray(node)) return node.some(hit)
      if (typeof node !== 'object' || node === null) return false
      const record = node as Record<string, unknown>
      if (record.type === 'template' && record.ref === name) return true
      return Object.values(record).some(hit)
    }
    return {
      rules: file.rules.flatMap((rule, index) => (hit(rule) ? [index] : [])),
      templates: Object.entries(file.templates).flatMap(([key, def]) =>
        key !== name && hit(def) ? [key] : [],
      ),
    }
  }

  /** Renames a template and every use of it. */
  function renameTemplate(from: string, to: string): boolean {
    if (from === to || to === '' || to in file.templates) return false
    const fix = (node: unknown): void => {
      if (Array.isArray(node)) node.forEach(fix)
      else if (typeof node === 'object' && node !== null) {
        const record = node as Record<string, unknown>
        if (record.type === 'template' && record.ref === from) record.ref = to
        Object.values(record).forEach(fix)
      }
    }
    fix(file.rules)
    fix(file.templates)
    file.templates = Object.fromEntries(
      Object.entries(file.templates).map(([key, def]) => [key === from ? to : key, def]),
    )
    return true
  }

  return {
    file,
    view,
    fileName,
    canUndo,
    canRedo,
    problems,
    yaml,
    undo,
    redo,
    load,
    addRule,
    duplicateRule,
    removeRule,
    moveRule,
    usesOf,
    renameTemplate,
  }
}

export type Store = ReturnType<typeof createStore>
