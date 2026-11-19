import { computed, onScopeDispose, shallowRef } from 'vue'
import { conditionAt, findReplaceable, type TemplateHint } from '../template-match'
import type { RuleFile } from '../types'

const STORAGE_KEY = 'template-hints-checked'

function checkDate(now: Date): string {
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-')
}

export function shouldCheck(last: string | null, now = new Date()): boolean {
  return last !== checkDate(now)
}

function lastCheck(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function locationKey(rule: number, path: readonly number[]): string {
  return `${rule}:${path.join('.')}`
}

export function useTemplateHints(file: RuleFile) {
  const snapshot = shallowRef<{ hint: TemplateHint; nodeKey: string; templateKey: string }[]>([])
  let checked = lastCheck()

  function nodeKey(hint: TemplateHint): string {
    const root =
      'rule' in hint ? file.rules?.[hint.rule]?.when : file.templates[hint.templateName]?.content
    return JSON.stringify(conditionAt(root, hint.path))
  }

  function refreshTemplateHints(): void {
    const templateKeys = new Map<string, string>()
    snapshot.value = findReplaceable(file).map((hint) => {
      let templateKey = templateKeys.get(hint.template)
      if (templateKey === undefined) {
        templateKey = JSON.stringify(file.templates[hint.template])
        templateKeys.set(hint.template, templateKey)
      }
      // Bindings can contain objects from the live expression. Keep them independent of edits.
      const variables = JSON.parse(JSON.stringify(hint.variables)) as Record<string, unknown>
      return { hint: { ...hint, variables }, nodeKey: nodeKey(hint), templateKey }
    })
    checked = checkDate(new Date())
    try {
      localStorage.setItem(STORAGE_KEY, checked)
    } catch {
      // The in-memory date still works when storage is unavailable.
    }
  }

  const templateHints = computed(() => {
    const templateKeys = new Map<string, string>()
    return snapshot.value.flatMap((entry) => {
      const { hint } = entry
      let templateKey = templateKeys.get(hint.template)
      if (templateKey === undefined) {
        templateKey = JSON.stringify(file.templates[hint.template])
        templateKeys.set(hint.template, templateKey)
      }
      return entry.templateKey === templateKey && entry.nodeKey === nodeKey(hint) ? [hint] : []
    })
  })

  const ruleHints = computed(() => {
    const hints = new Map<string, TemplateHint>()
    for (const hint of templateHints.value)
      if ('rule' in hint) hints.set(locationKey(hint.rule, hint.path), hint)
    return hints
  })

  function hintsFor(template: string): TemplateHint[] {
    return templateHints.value.filter((hint) => hint.template === template)
  }

  function hintAt(rule: number, path: readonly number[]): TemplateHint | undefined {
    return ruleHints.value.get(locationKey(rule, path))
  }

  function checkIfDue(): void {
    if (shouldCheck(checked)) refreshTemplateHints()
  }

  function onVisibilityChange(): void {
    if (document.visibilityState === 'visible') checkIfDue()
  }

  checkIfDue()
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
    onScopeDispose(() => document.removeEventListener('visibilitychange', onVisibilityChange))
  }

  return { templateHints, hintsFor, hintAt, refreshTemplateHints }
}
