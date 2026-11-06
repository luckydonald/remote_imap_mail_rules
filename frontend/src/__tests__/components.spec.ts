import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { createAppRouter } from '@/router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AppShell from '@/components/AppShell.vue'
import ConditionNode from '@/components/ConditionNode.vue'
import FieldValue from '@/components/FieldValue.vue'
import MailLog from '@/components/MailLog.vue'
import TemplateRenameBox from '@/components/TemplateRenameBox.vue'
import SourceMenu from '@/components/SourceMenu.vue'
import { useStore } from '@/model/store'
import { useMailStore } from '@/model/mail-store'
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

describe('template use with an example mail', () => {
  const when = () =>
    reactive<Expression>({ type: 'all', conditions: [{ type: 'bool', field: 'seen' }] })

  function openMail(): void {
    const mail = useMailStore()
    mail.active = true
    mail.accountId = 'a'
    mail.folder = 'INBOX'
    mail.detail = {
      subject: 'Hello',
      sender: { name: 'Max', address: 'max@example.com' },
      flags: [],
      attachments: [],
      headers: [{ name: 'Subject', value: 'Hello' }],
    } as never
  }

  function addTemplates(store: ReturnType<typeof useStore>): void {
    for (const name of ['t1', 't2'])
      store.file.templates[name] = {
        type: 'template',
        defaults: {},
        content: { type: 'text', field: 'subject', operator: 'equals', value: { var: 'subj' } },
      } as never
  }

  it('fills a template use created by changing the type', async () => {
    const node = when()
    const { store, wrapper } = withStore(() => h(ConditionNode, { modelValue: node }))
    addTemplates(store)
    openMail()
    const selects = wrapper
      .findAll('select')
      .filter((item) => item.find('option[value="template"]').exists())
    const select = selects[selects.length - 1]!
    await select.setValue('template')
    await flushPromises()
    expect(JSON.stringify(node)).toContain('"subj":"Hello"')
  })
})

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

  it('cuts a child into the clipboard store and pastes it into another group', async () => {
    const when = reactive<Expression>({
      type: 'all',
      conditions: [
        { type: 'any', conditions: [{ type: 'bool', field: 'seen' }] },
        { type: 'bool', field: 'flagged' },
      ],
    })
    const { store, wrapper } = withStore(() => h(ConditionNode, { modelValue: when }))
    const pasteButtons = () => wrapper.findAll('button.paste')
    // The inner `any` is cut, with its sub-block.
    await wrapper.findAll('button.cut')[1]!.trigger('click')
    expect(when.type === 'all' && when.conditions).toHaveLength(1)
    // Pasting into the root appends the whole copy.
    await pasteButtons()[0]!.trigger('click')
    await flushPromises()
    expect(when.type === 'all' && when.conditions[1]).toEqual({
      type: 'any',
      conditions: [{ type: 'bool', field: 'seen' }],
    })
    expect(store).toBeDefined()
  })

  it('replaces a cut root by a default condition', async () => {
    const updates: Expression[] = []
    const { wrapper } = withStore(() =>
      h(ConditionNode, {
        modelValue: { type: 'bool', field: 'seen' },
        'onUpdate:modelValue': (value: Expression) => updates.push(value),
      }),
    )
    await wrapper.find('button.cut').trigger('click')
    expect(updates[0]?.type).toBe('text')
  })

  it('shows a hint when there is nothing to paste', async () => {
    const when = reactive<Expression>({
      type: 'all',
      conditions: [{ type: 'bool', field: 'seen' }],
    })
    const { wrapper } = withStore(() => h(ConditionNode, { modelValue: when }))
    vi.stubGlobal('navigator', { clipboard: { readText: async () => 'nope' } })
    await wrapper.find('button.paste').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Nothing to paste')
    vi.unstubAllGlobals()
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

describe('TemplateRenameBox', () => {
  const YAML = `templates:
  t: &t
    type: template
    content: {type: text, field: subject, operator: contains, value: !var word}
rules:
  - name: r
    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]
    when:
      <<: *t
      variables: {word: hello}
`

  it('asks, folds to a chip and renames on Yes', async () => {
    const { store, wrapper } = withStore(() => h(TemplateRenameBox, { template: 't' }))
    store.load(YAML)
    expect(wrapper.find('.rename').exists()).toBe(false)
    const content = store.file.templates.t?.content as { value: unknown }
    content.value = { var: 'phrase' }
    await flushPromises()
    expect(wrapper.find('.rename-box').text()).toContain('word → phrase')
    expect(wrapper.find('.rename-box .count-badge').text()).toBe('1')
    await wrapper.findAll('.rename-box kbd')[1]?.trigger('click')
    expect(wrapper.find('.rename-chip').text()).toContain('rename 1')
    await wrapper.find('.rename-chip').trigger('click')
    await wrapper.findAll('.rename-box kbd')[0]?.trigger('click')
    expect(wrapper.find('.rename').exists()).toBe(false)
    expect(store.yaml).toContain('phrase: hello')
  })
})
