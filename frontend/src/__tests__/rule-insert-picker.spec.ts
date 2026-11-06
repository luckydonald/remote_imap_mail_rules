import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RuleInsertPicker from '@/components/RuleInsertPicker.vue'
import type { Rule } from '@/model/types'

const leaf = (value: string) =>
  ({ type: 'text', field: 'subject', operator: 'equals', value }) as const

const rules: Rule[] = [
  {
    name: 'two',
    locations: [],
    when: { type: 'all', conditions: [leaf('a'), { type: 'any', conditions: [leaf('b')] }] },
  },
  { name: 'lone', enabled: false, locations: [], when: leaf('c') },
]

describe('RuleInsertPicker', () => {
  it('has an insert area before, between and after the children of every group', () => {
    const wrapper = mount(RuleInsertPicker, { props: { rules } })
    const first = wrapper.findAll('.insert-rule')[0]!
    // root all: 2 children, so 3 areas; the any group inside: 1 child, so 2 areas
    expect(first.findAll('.insert-point')).toHaveLength(5)
    const lone = wrapper.findAll('.insert-rule')[1]!
    expect(lone.findAll('.insert-point')).toHaveLength(2)
    expect(lone.text()).toContain('(disabled)')
  })

  it('emits the rule, the group path and the position that was clicked', async () => {
    const wrapper = mount(RuleInsertPicker, { props: { rules } })
    await wrapper.get('[aria-label="Insert into two, child 2, position 1"]').trigger('click')
    await wrapper.get('[aria-label="Insert into two, whole rule, position 2"]').trigger('click')
    await wrapper.get('[aria-label="Insert into lone, whole rule, position 2"]').trigger('click')
    expect(wrapper.emitted('pick')).toEqual([
      [{ ruleIndex: 0, path: [1], index: 0 }],
      [{ ruleIndex: 0, path: [], index: 1 }],
      [{ ruleIndex: 1, path: [], index: 1 }],
    ])
  })
})
