import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useStore } from '@/model/store'

beforeEach(() => setActivePinia(createPinia()))

describe('store', () => {
  it('undoes and redoes', async () => {
    const store = useStore()
    store.addRule()
    await nextTick()
    expect(store.file.rules).toHaveLength(1)
    expect(store.canUndo).toBe(true)
    store.undo()
    expect(store.file.rules).toHaveLength(0)
    store.redo()
    expect(store.file.rules).toHaveLength(1)
  })

  it('renames a template with its uses', () => {
    const store = useStore()
    store.load(
      'templates:\n  a: &a\n    type: template\n    content: {type: bool, field: seen}\nrules:\n  - name: r\n    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]\n    when:\n      <<: *a\n',
    )
    expect(store.usesOf('a').rules).toEqual([0])
    expect(store.renameTemplate('a', 'b')).toBe(true)
    expect(Object.keys(store.file.templates)).toEqual(['b'])
    expect(store.usesOf('b').rules).toEqual([0])
    expect(store.yaml).toContain('<<: *template-b')
  })
})

describe('store server state', () => {
  it('is only dirty on a server file, and clean again after saving', () => {
    const store = useStore()
    store.load('rules: []\n', 'local.yml')
    store.addRule()
    expect(store.serverFile).toBeNull()
    expect(store.dirty).toBe(false)
    store.markSaved('rules.yml', '')
    expect(store.dirty).toBe(true)
    store.markSaved()
    expect(store.dirty).toBe(false)
    store.addRule()
    expect(store.dirty).toBe(true)
  })

  it('leaves server mode when a local file is loaded', () => {
    const store = useStore()
    store.markSaved('rules.yml')
    store.load('rules: []\n', 'local.yml')
    expect(store.serverFile).toBeNull()
  })
})

describe('store documents', () => {
  const ONE =
    'rules:\n  - name: one\n    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]\n    when: {type: bool, field: seen}\n'

  it('applies text without leaving the server document', () => {
    const store = useStore()
    store.markSaved('rules.yml', '', '# raw\nrules: []\n')
    store.applyText(ONE)
    expect(store.serverFile).toBe('rules.yml')
    expect(store.serverRaw).toBe('# raw\nrules: []\n')
    expect(store.dirty).toBe(true)
    expect(() => store.applyText('rules: [')).toThrow(/\S/)
    expect(store.file.rules).toHaveLength(1)
  })

  it('opens a file beside the server document and brings the edits back', () => {
    const store = useStore()
    store.load(ONE, 'server.yml')
    store.markSaved('server.yml')
    store.addRule()
    expect(store.dirty).toBe(true)

    store.openDocument('rules: []\n', 'mine.yml')
    expect(store.serverFile).toBeNull()
    expect(store.file.rules).toHaveLength(0)
    expect(store.documents.map((item) => item.name)).toEqual(['mine.yml'])
    expect(store.canUndo).toBe(false)
    expect(store.isEdited('server')).toBe(true)

    store.switchTo('server')
    expect(store.serverFile).toBe('server.yml')
    expect(store.file.rules).toHaveLength(2)
    expect(store.dirty).toBe(true)
    expect(store.fileName).toBe('server.yml')
  })

  it('keeps the edits of an ad-hoc document and tells edited ones', () => {
    const store = useStore()
    store.openDocument(ONE, 'a.yml')
    store.openDocument('rules: []\n')
    const [, first, second] = store.documents
    expect(second!.name).toBeNull()
    store.addRule()
    expect(store.isEdited(second!.id)).toBe(true)
    expect(store.isEdited(first!.id)).toBe(false)
    store.switchTo(first!.id)
    expect(store.file.rules).toHaveLength(1)
    expect(store.isEdited(second!.id)).toBe(true)
    store.switchTo(second!.id)
    expect(store.file.rules).toHaveLength(1)
    expect(store.fileName).toBe('rules.yml')
  })

  it('does not change anything when the file to open is broken', () => {
    const store = useStore()
    store.load(ONE, 'a.yml')
    expect(() => store.openDocument('rules: [', 'bad.yml')).toThrow(/\S/)
    expect(store.documents).toHaveLength(0)
    expect(store.file.rules).toHaveLength(1)
  })
})
