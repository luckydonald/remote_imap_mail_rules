/** The last choices of the `Rule ▾` > "Add to existing rule" dialog, kept for the next mail (memory only). Part of the central store (`index.ts`). */

import { ref } from 'vue'
import type { Granularity } from '../fill-from-mail'

export function useAddToRule() {
  const addToRuleKind = ref<'condition' | 'template'>('condition')
  const addToRuleField = ref('from')
  const addToRuleGranularity = ref<Granularity>('address')
  const addToRuleTemplate = ref('')
  return { addToRuleKind, addToRuleField, addToRuleGranularity, addToRuleTemplate }
}
