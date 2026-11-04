import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { createAppRouter } from '@/router'
import { beforeEach, describe, expect, it } from 'vitest'
import AppShell from '@/components/AppShell.vue'
import ConditionNode from '@/components/ConditionNode.vue'
import FieldValue from '@/components/FieldValue.vue'
import MailLog from '@/components/MailLog.vue'
import SourceMenu from '@/components/SourceMenu.vue'
import { useStore } from '@/model/store'
import { defineComponent, h, reactive } from 'vue'
import { ALLOW_VARS } from '@/model/context'
import type { Expression } from '@/model/types'

beforeEach(() => setActivePinia(createPinia()))

function withStore(child: () => ReturnType<typeof h>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useStore()
  const Host = defineComponent({ setup: () => child })
  return { store, wrapper: mount(Host, { global: { plugins: [pinia] } }) }
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
    const router = createAppRouter(createMemoryHistory())
    await router.push('/rules')
    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router] } })
    await wrapper.find('button.add').trigger('click')
    expect(wrapper.find('.rule-editor').exists()).toBe(true)
    // The new rule has an empty account id, which is not a UUID yet.
    expect(wrapper.find('.topbar .badge.error').exists()).toBe(true)
    // The store's selection shows in the URL.
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/rules/0')
  })

  it('opens the view of the route', async () => {
    const router = createAppRouter(createMemoryHistory())
    await router.push('/rules/templates')
    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router] } })
    expect(wrapper.find('.templates').exists()).toBe(true)
    await router.push('/accounts')
    await flushPromises()
    expect(wrapper.find('.body').exists()).toBe(false)
  })
})

describe('MailLog', () => {
  it('lists the entries and hides itself without any', () => {
    const entry = (
      id: string,
      kind: 'first_seen' | 'rule_match',
      rule: string | null,
      detail = {},
    ) => ({
      id,
      kind,
      rule_name: rule,
      detail,
      created_at: '2026-11-03T10:00:00Z',
    })
    const wrapper = mount(MailLog, {
      props: {
        events: [
          entry('a', 'first_seen', null),
          entry('b', 'rule_match', 'invoices', { match_kind: 'new' }),
        ],
      },
    })
    expect(wrapper.findAll('li').map((item) => item.find('.what').text())).toEqual([
      'First seen',
      'Matched the rule "invoices" (new)',
    ])
    expect(
      mount(MailLog, { props: { events: [] } })
        .find('.mail-log')
        .exists(),
    ).toBe(false)
  })
})

describe('SourceMenu', () => {
  const mountMenu = () => withStore(() => h(SourceMenu))

  it('is a plain label for the scratch file, without a server', () => {
    const { wrapper } = mountMenu()
    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.text()).toBe('🕳️ In Memory')
  })

  it('names the file on the server, the database and the ad-hoc files', async () => {
    const { store, wrapper } = mountMenu()
    store.backend = { kind: 'file', name: 'somefile.yml' }
    store.markSaved('somefile.yml')
    await flushPromises()
    expect(wrapper.text()).toBe('📄 somefile.yml')

    store.backend = { kind: 'database', name: null }
    await flushPromises()
    expect(wrapper.text()).toBe('🗄️ Database')

    store.openDocument('rules: []\n', 'mine.yml')
    await flushPromises()
    expect(wrapper.get('summary').text()).toBe('🕳️ In Memory · mine.yml')
    expect(wrapper.findAll('li button').map((item) => item.text())).toEqual([
      '🗄️ Database',
      '🕳️ In Memory · mine.yml',
    ])
  })

  it('switches back to the server and shows the edited dot', async () => {
    const { store, wrapper } = mountMenu()
    store.backend = { kind: 'file', name: 'somefile.yml' }
    store.markSaved('somefile.yml')
    store.addRule()
    store.openDocument('rules: []\n', 'mine.yml')
    await flushPromises()
    const [server] = wrapper.findAll('li button')
    expect(server!.text()).toBe('📄 somefile.yml ●')
    await server!.trigger('click')
    expect(store.serverFile).toBe('somefile.yml')
    expect(store.file.rules).toHaveLength(1)
    expect(wrapper.get('summary').text()).toBe('📄 somefile.yml')
  })
})
