import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RuleIndex from '@/components/RuleIndex.vue'
import RuleInsertPicker from '@/components/RuleInsertPicker.vue'
import type { Rule } from '@/model/types'

const leaf = { type: 'text', field: 'subject', operator: 'equals', value: 'a' } as const
const rules: Rule[] = [
  { name: 'one', locations: [], when: leaf },
  { name: 'two', enabled: false, locations: [], when: leaf },
]

describe('RuleIndex', () => {
  it('lists the rules and emits the index of the one clicked', async () => {
    const wrapper = mount(RuleIndex, { props: { rules } })
    expect(wrapper.findAll('button')).toHaveLength(2)
    expect(wrapper.text()).toContain('(disabled)')
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(wrapper.emitted('open')).toEqual([[1]])
  })
})

describe('RuleInsertPicker only', () => {
  it('shows just that rule and keeps the real rule index', async () => {
    const wrapper = mount(RuleInsertPicker, { props: { rules, only: 1 } })
    expect(wrapper.findAll('.insert-rule')).toHaveLength(1)
    await wrapper.get('.insert-point').trigger('click')
    expect(wrapper.emitted('pick')).toEqual([[{ ruleIndex: 1, path: [], index: 0 }]])
  })
})
