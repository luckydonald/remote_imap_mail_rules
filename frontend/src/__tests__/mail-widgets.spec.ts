import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import MailChip from '@/components/MailChip.vue'
import MailFolderTree from '@/components/MailFolderTree.vue'
import SegmentedToggle from '@/components/SegmentedToggle.vue'
import type { Folder } from '@/model/mail-api'
import { framePolicy } from '@/model/mail-format'
import { useMailStore } from '@/model/store'

const folder = (name: string, extra: Partial<Folder> = {}): Folder => ({
  name,
  display_name: name,
  delimiter: '/',
  special_use: null,
  selectable: true,
  messages: null,
  unseen: null,
  ...extra,
})

describe('SegmentedToggle', () => {
  it('highlights the current option and emits the other one', async () => {
    const wrapper = mount(SegmentedToggle, {
      props: {
        modelValue: 'html',
        label: 'Show as',
        options: [
          { value: 'text', label: 'Text' },
          { value: 'html', label: 'HTML' },
        ],
      },
    })
    expect(wrapper.find('button.on').text()).toBe('HTML')
    await wrapper.findAll('button')[0]!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['text']])
  })
})

describe('MailFolderTree', () => {
  const folders = [folder('INBOX'), folder('Archive/2025'), folder('Archive/2026')]

  it('nests folders under a parent that is not a folder itself, and collapses it', async () => {
    const wrapper = mount(MailFolderTree, { props: { folders } })
    const labels = () => wrapper.findAll('[role=treeitem] .label').map((item) => item.text())
    expect(labels()).toEqual(['Archive', '2025', '2026', 'INBOX'])
    await wrapper.find('[role=treeitem] button.twisty').trigger('click')
    expect(labels()).toEqual(['Archive', 'INBOX'])
  })

  it('selects a folder but not the current one, and filters', async () => {
    const wrapper = mount(MailFolderTree, { props: { folders, current: 'INBOX' } })
    await wrapper
      .findAll('[role=treeitem]')
      .find((item) => item.text().includes('2026'))!
      .trigger('click')
    expect(wrapper.emitted('select')).toEqual([['Archive/2026']])
    await wrapper
      .findAll('[role=treeitem]')
      .find((item) => item.text().includes('INBOX'))!
      .trigger('click')
    expect(wrapper.emitted('select')).toHaveLength(1)
    await wrapper.find('input').setValue('2025')
    expect(wrapper.findAll('[role=treeitem] .label').map((item) => item.text())).toEqual([
      'Archive',
      '2025',
    ])
  })
})

describe('framePolicy', () => {
  it('allows remote images only on request', () => {
    expect(framePolicy(false)).not.toContain('https:')
    expect(framePolicy(true)).toContain('https:')
    expect(framePolicy(true)).toContain("default-src 'none'")
  })
})

describe('MailChip', () => {
  it('shows the subject of the mail to fill from and drops it with the ×', async () => {
    setActivePinia(createPinia())
    const mail = useMailStore()
    mail.active = true
    mail.accountId = 'a'
    mail.folder = 'INBOX'
    mail.detail = { subject: 'Hello there' } as never
    const wrapper = mount(MailChip)
    expect(wrapper.text()).toContain('Hello there')
    await wrapper.get('button.remove').trigger('click')
    expect(mail.fillDetached).toBe(true)
    expect(wrapper.find('.mail-chip').exists()).toBe(false)
  })
})
