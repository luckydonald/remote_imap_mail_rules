import { defineStore } from 'pinia'
import { computed, reactive, ref, shallowRef, watch } from 'vue'
import { templateVariables, validateRules } from './validate'
import { parseRulesWithComments, stringifyRules } from './yaml-io'
import type { CommentMap } from './comments'
import { newExpression } from './catalog'
import type { Rule, RuleFile, TemplateUse } from './types'

export type View = { kind: 'rule'; index: number } | { kind: 'templates' } | { kind: 'yaml' }

const HISTORY_LIMIT = 100

/** A template variable that was renamed in the template and whose uses are not renamed yet. */
export interface PendingRename {
  from: string
  to: string
  /** Whether Yes renames this one (the ✓ of the box). */
  include: boolean
}

/** Where the rules of the server live: its rules file or its database. */
export interface Backend {
  kind: 'file' | 'database'
  /** The file name on the server, `null` for the database. */
  name: string | null
}

/** An ad-hoc file of this session, edited in memory and never written to the server. */
export interface MemoryDocument {
  id: string
  /** The name of the opened file, `null` for one made with New. */
  name: string | null
  /** The YAML as of the last switch away from it; the live one is `yaml` of the store. */
  text: string
  /** The YAML as opened, to tell edited ones. */
  baseline: string
}

/** The server document while another one is live. */
interface ServerStash {
  name: string
  text: string
  saved: string
  raw: string
}

/** The entry of the source menu that stands for the server's rules. */
export const SERVER = 'server'

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

/** The rule editor's document and its history, one per app (a Pinia setup store, so unwrapped refs: `store.view`, not `store.view.value`). */
export const useStore = defineStore('rules', () => {
  const file = reactive<RuleFile>(emptyFile())
  const view = ref<View>({ kind: 'yaml' })
  const fileName = ref('rules.yml')
  /** The file name on the server while the editor works on its rules file, else `null` (a local file never writes to disk). */
  const serverFile = ref<string | null>(null)
  /** The YAML as last loaded from or saved to the server. */
  const savedYaml = ref('')
  /** The text of the server's rules exactly as it was last read or written, with its own formatting and comments. */
  const serverRaw = ref('')
  /** What the server keeps the rules in; `null` without a server. */
  const backend = ref<Backend | null>(null)
  /** The ad-hoc files of this session, besides the live one when it was not switched away from yet. */
  const documents = reactive<MemoryDocument[]>([])
  /** The id of the live ad-hoc file; `null` before one was stashed (the pristine scratch file) or while the server's rules are live. */
  const memoryId = ref<string | null>(null)
  const serverStash = shallowRef<ServerStash | null>(null)
  /** Comments of the loaded text, written back when generating the YAML. */
  const comments = shallowRef<CommentMap | undefined>()
  const past: string[] = []
  const future: string[] = []
  const canUndo = ref(false)
  const canRedo = ref(false)
  let last = JSON.stringify(file)
  let applying = false

  /** Renames of template variables the uses were not told about yet, by template name. */
  const pendingRenames = ref<Record<string, PendingRename[]>>({})
  /** Whether the rename box of a template is folded to its chip. */
  const renamesCollapsed = ref<Record<string, boolean>>({})

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

  /** Runs several changes as one undo step. */
  function batch(change: () => void): void {
    const before = last
    applying = true
    try {
      change()
    } finally {
      applying = false
    }
    const json = JSON.stringify(file)
    if (json === before) return
    past.push(before)
    if (past.length > HISTORY_LIMIT) past.shift()
    future.length = 0
    last = json
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
    serverFile.value = null
    pendingRenames.value = {}
    renamesCollapsed.value = {}
    view.value = file.rules.length > 0 ? { kind: 'rule', index: 0 } : { kind: 'yaml' }
  }

  const problems = computed(() => validateRules(file))
  const yaml = computed(() => stringifyRules(file, comments.value))
  const dirty = computed(() => serverFile.value !== null && yaml.value !== savedYaml.value)

  /** Marks the current content as the one on the server; `raw` is the text the server holds, which may be formatted differently. */
  function markSaved(
    name: string | null = serverFile.value,
    text: string = yaml.value,
    raw: string = text,
  ): void {
    serverFile.value = name
    savedYaml.value = text
    serverRaw.value = raw
  }

  /** Like `load`, but the server's rules stay the live document, so Save and the dirty marker keep working. Throws on bad YAML, changing nothing. */
  function applyText(text: string): void {
    const name = serverFile.value
    const saved = savedYaml.value
    const raw = serverRaw.value
    const kept = view.value
    load(text)
    // Whoever edits the text stays in the YAML view instead of being sent to the first rule.
    if (kept.kind === 'yaml') view.value = kept
    if (name !== null) markSaved(name, saved, raw)
  }

  function clearHistory(): void {
    past.length = 0
    future.length = 0
    last = JSON.stringify(file)
    sync()
  }

  /** Remembers the live document, so it can come back with its edits. */
  function stash(): void {
    if (serverFile.value !== null) {
      serverStash.value = {
        name: serverFile.value,
        text: yaml.value,
        saved: savedYaml.value,
        raw: serverRaw.value,
      }
      return
    }
    let document = documents.find((item) => item.id === memoryId.value)
    if (!document) {
      document = { id: crypto.randomUUID(), name: null, text: yaml.value, baseline: yaml.value }
      if (fileName.value !== 'rules.yml') document.name = fileName.value
      documents.push(document)
      memoryId.value = document.id
    }
    document.text = yaml.value
  }

  /** Opens a file as a new ad-hoc document beside the server's rules, which stay as they are. Throws on bad YAML, changing nothing. */
  function openDocument(text: string, name: string | null = null): void {
    parseRulesWithComments(text)
    stash()
    load(text, name ?? 'rules.yml')
    const document = { id: crypto.randomUUID(), name, text: yaml.value, baseline: yaml.value }
    documents.push(document)
    memoryId.value = document.id
    clearHistory()
  }

  /** Makes the server's rules (`SERVER`) or an ad-hoc document the live one; the other one is kept with its edits. */
  function switchTo(id: string): void {
    if (id === (serverFile.value !== null ? SERVER : memoryId.value)) return
    if (id === SERVER) {
      const kept = serverStash.value
      if (!kept) return
      stash()
      load(kept.text, kept.name)
      markSaved(kept.name, kept.saved, kept.raw)
    } else {
      const document = documents.find((item) => item.id === id)
      if (!document) return
      stash()
      load(document.text, document.name ?? 'rules.yml')
      memoryId.value = document.id
    }
    clearHistory()
  }

  /** Whether the document of this menu entry has edits that are not saved (server) or not as opened (ad-hoc). */
  function isEdited(id: string): boolean {
    const live = serverFile.value !== null ? SERVER : memoryId.value
    if (id === SERVER) {
      if (id === live) return dirty.value
      const kept = serverStash.value
      return kept !== null && kept.text !== kept.saved
    }
    const document = documents.find((item) => item.id === id)
    if (!document) return false
    return (id === live ? yaml.value : document.text) !== document.baseline
  }

  /** Whether any document, the server's or an ad-hoc one, has edits that closing the page would lose. */
  const anyEdited = computed(() => isEdited(SERVER) || documents.some((item) => isEdited(item.id)))

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
    for (const state of [pendingRenames, renamesCollapsed] as const) {
      const record = state.value as Record<string, unknown>
      if (from in record) {
        record[to] = record[from]
        delete record[from]
      }
    }
    file.templates = Object.fromEntries(
      Object.entries(file.templates).map(([key, def]) => [key === from ? to : key, def]),
    )
    return true
  }

  /** Every use of a template, in the rules and in other templates. */
  function usesOfTemplate(name: string): TemplateUse[] {
    const found: TemplateUse[] = []
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) node.forEach(walk)
      else if (typeof node === 'object' && node !== null) {
        const record = node as Record<string, unknown>
        if (record.type === 'template' && record.ref === name)
          found.push(record as unknown as TemplateUse)
        Object.values(record).forEach(walk)
      }
    }
    walk(file.rules)
    walk(file.templates)
    return found
  }

  /** How many uses of the template bind the variable. */
  function countUsages(template: string, variable: string): number {
    return usesOfTemplate(template).filter((use) => variable in (use.variables ?? {})).length
  }

  function noticeRename(template: string, before: string[], after: string[]): void {
    const gone = before.filter((name) => !after.includes(name))
    const added = after.filter((name) => !before.includes(name))
    const [from, to] = [gone[0], added[0]]
    if (gone.length !== 1 || added.length !== 1 || from === undefined || to === undefined) return
    const list = pendingRenames.value[template] ?? []
    const chained = list.find((entry) => entry.to === from)
    if (chained) {
      chained.to = to
      if (chained.to === chained.from) list.splice(list.indexOf(chained), 1)
    } else if (
      from !== '' &&
      (countUsages(template, from) > 0 || from in (file.templates[template]?.defaults ?? {}))
    ) {
      list.push({ from, to, include: true })
    }
    if (list.length > 0) pendingRenames.value[template] = list
    else delete pendingRenames.value[template]
  }

  watch(
    () =>
      Object.fromEntries(Object.keys(file.templates).map((n) => [n, templateVariables(file, n)])),
    (now, old) => {
      if (applying) return
      for (const [name, after] of Object.entries(now)) {
        const before = old[name]
        if (before && before.join('\n') !== after.join('\n')) noticeRename(name, before, after)
      }
    },
    { flush: 'sync' },
  )

  /** Renames the included pending variables in every use and in the defaults of the template, as one undo step. */
  function renameVariables(template: string): void {
    const def = file.templates[template]
    const list = pendingRenames.value[template] ?? []
    batch(() => {
      for (const entry of list) {
        if (!entry.include || entry.to === '') continue
        for (const use of usesOfTemplate(template)) {
          if (!(entry.from in (use.variables ?? {})) || entry.to in use.variables) continue
          use.variables = Object.fromEntries(
            Object.entries(use.variables).map(([k, v]) => [k === entry.from ? entry.to : k, v]),
          )
        }
        if (def?.defaults && entry.from in def.defaults && !(entry.to in def.defaults)) {
          def.defaults = Object.fromEntries(
            Object.entries(def.defaults).map(([k, v]) => [k === entry.from ? entry.to : k, v]),
          )
        }
      }
    })
    const rest = list.filter((entry) => !entry.include)
    if (rest.length > 0) pendingRenames.value[template] = rest
    else delete pendingRenames.value[template]
  }

  /** Whether a variable of a use has no value yet. */
  function isUnfilled(value: unknown): boolean {
    return value === undefined || value === ''
  }

  /**
   * Moves the value of a variable the template no longer has to an existing one.
   * Returns `conflict` without changing anything when the target is filled and `keep` (the orphan's or the target's value) was not given.
   */
  function resolveOrphan(
    use: TemplateUse,
    key: string,
    target: string,
    keep?: 'orphan' | 'target',
  ): 'done' | 'conflict' {
    const filled = !isUnfilled(use.variables[target])
    if (filled && keep === undefined) return 'conflict'
    batch(() => {
      if (!filled || keep === 'orphan') use.variables[target] = use.variables[key]
      delete use.variables[key]
    })
    return 'done'
  }

  /** Drops a variable of a use the template no longer has. */
  function dropOrphan(use: TemplateUse, key: string): void {
    delete use.variables[key]
  }

  return {
    pendingRenames,
    renamesCollapsed,
    countUsages,
    renameVariables,
    resolveOrphan,
    dropOrphan,
    file,
    view,
    fileName,
    serverFile,
    serverRaw,
    savedYaml,
    backend,
    documents,
    memoryId,
    serverStash,
    dirty,
    markSaved,
    applyText,
    openDocument,
    switchTo,
    isEdited,
    anyEdited,
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
})

export type Store = ReturnType<typeof useStore>
