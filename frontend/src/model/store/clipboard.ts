/** Cut and paste of rule blocks: the last cut block in memory, and as YAML on the real clipboard if the settings allow it. Part of the central store (`index.ts`). */

import { computed, shallowRef } from 'vue'
import { expressionTypes } from '../catalog'
import { validateRules } from '../validate'
import { parseYamlData, stringifyExpression } from '../yaml-io'
import type { Expression, Rule } from '../types'
import type { usePrefs } from './prefs'

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Template uses are checked against the file they land in, so here they only stand for a valid leaf. */
function stubUses(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(stubUses)
  if (!isObject(node)) return node
  if (node.type === 'template') return { type: 'bool', field: 'seen' }
  return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, stubUses(value)]))
}

/** The rule block in the YAML text, or `null` when the text is anything else. Never throws. */
export function parseExpressionText(text: string): Expression | null {
  let data: unknown
  try {
    data = parseYamlData(text)
  } catch {
    return null
  }
  if (!isObject(data) || !(expressionTypes as readonly string[]).includes(String(data.type)))
    return null
  const rule = {
    name: 'paste',
    enabled: true,
    locations: [{ account_id: '', folder: 'INBOX', recursive: false }],
    when: stubUses(data),
    actions: [],
  } as unknown as Rule
  const problems = validateRules({ templates: {}, rules: [rule] })
  return problems.some((problem) => problem.path.startsWith('/rules/0/when'))
    ? null
    : (data as unknown as Expression)
}

const copyOf = (expression: Expression): Expression => JSON.parse(JSON.stringify(expression))

export function useClipboard(prefs: ReturnType<typeof usePrefs>) {
  /** The last cut block, kept for this session. */
  const clipboardBlock = shallowRef<Expression | null>(null)
  /** Whether a paste may find something: a cut block, or a clipboard that is allowed to be read. */
  const canPaste = computed(() => clipboardBlock.value !== null || prefs.readPaste.value === 'on')

  /** Remembers a copy of the block and, if allowed, puts its YAML on the clipboard. A blocked clipboard is no error. */
  async function cutBlock(expression: Expression): Promise<void> {
    clipboardBlock.value = copyOf(expression)
    if (prefs.copyCut.value !== 'on') return
    try {
      await navigator.clipboard.writeText(stringifyExpression(expression))
    } catch {
      // The block is still in memory.
    }
  }

  /** A fresh copy of the block to paste: from the clipboard if it holds one and reading is allowed, else the last cut. */
  async function readBlock(): Promise<Expression | null> {
    if (prefs.readPaste.value === 'on') {
      try {
        const parsed = parseExpressionText(await navigator.clipboard.readText())
        if (parsed) return parsed
      } catch {
        // No permission or no API: use the cut block.
      }
    }
    return clipboardBlock.value ? copyOf(clipboardBlock.value) : null
  }

  return { clipboardBlock, canPaste, cutBlock, readBlock }
}
