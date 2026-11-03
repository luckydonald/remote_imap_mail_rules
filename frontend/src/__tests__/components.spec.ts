import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppShell from '@/components/AppShell.vue'
import ConditionNode from '@/components/ConditionNode.vue'
import FieldValue from '@/components/FieldValue.vue'
import { provideStore } from '@/model/context'
import { createStore } from '@/model/store'
import { defineComponent, h, reactive } from 'vue'
import { ALLOW_VARS } from '@/model/context'
import type { Expression } from '@/model/types'

function withStore(child: () => ReturnType<typeof h>) {
  const store = createStore()
  const Host = defineComponent({
    setup() {
      provideStore(store)
      return child
    },
  })
  return { store, wrapper: mount(Host) }
}

describe('ConditionNode', () => {
  it('renders nested groups and adds a condition', async () => {
    const when = reactive<Expression>({
      type: 'all',
      conditions: [{ type: 'any', conditions: [{ type: 'bool', field: 'seen' }] }],
    })
    const { wrapper } = withStore(() => h(ConditionNode, { modelValue: when }))
    expect(wrapper.findAll('.node')).toHaveLength(3)
    await wrapper.findAll('button.add')[0]!.trigger('click')
    expect(wrapper.findAll('.node')).toHaveLength(4)
  })

  it('emits a new expression when the type changes', async () => {
    const updates: Expression[] = []
    const { wrapper } = withStore(() =>
      h(ConditionNode, {
        modelValue: { type: 'bool', field: 'seen' } as Expression,
        'onUpdate:modelValue': (value: Expression) => updates.push(value),
      }),
    )
    await wrapper.find("select[aria-label='Condition type']").setValue('number')
    expect(updates[0]?.type).toBe('number')
  })
})

describe('FieldValue', () => {
  const slots = { default: "<i class='literal'>slot</i>" }

  it('offers no variables outside of templates', () => {
    const wrapper = mount(FieldValue, { props: { modelValue: 'x', fallback: 'x' }, slots })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('toggles between a value and a variable inside templates', async () => {
    const wrapper = mount(FieldValue, {
      props: { modelValue: 'x', fallback: 'x' },
      slots,
      global: { provide: { [ALLOW_VARS as symbol]: true } },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ var: '' }])
    await wrapper.setProps({ modelValue: { var: 'name' } })
    expect(wrapper.find('.literal').exists()).toBe(false)
    expect((wrapper.find('input.var-name').element as HTMLInputElement).value).toBe('name')
  })
})

describe('AppShell', () => {
  it('creates a rule and shows it as valid or with problems', async () => {
    const wrapper = mount(AppShell)
    await wrapper.find('button.add').trigger('click')
    expect(wrapper.find('.rule-editor').exists()).toBe(true)
    // The new rule has an empty account id, which is not a UUID yet.
    expect(wrapper.find('.topbar .badge.error').exists()).toBe(true)
  })
})
