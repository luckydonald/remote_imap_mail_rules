import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createStore } from '@/model/store'

describe('store', () => {
  it('undoes and redoes', async () => {
    const store = createStore()
    store.addRule()
    await nextTick()
    expect(store.file.rules).toHaveLength(1)
    expect(store.canUndo.value).toBe(true)
    store.undo()
    expect(store.file.rules).toHaveLength(0)
    store.redo()
    expect(store.file.rules).toHaveLength(1)
  })

  it('renames a template with its uses', () => {
    const store = createStore()
    store.load(
      'templates:\n  a: &a\n    type: template\n    content: {type: bool, field: seen}\nrules:\n  - name: r\n    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]\n    when:\n      <<: *a\n',
    )
    expect(store.usesOf('a').rules).toEqual([0])
    expect(store.renameTemplate('a', 'b')).toBe(true)
    expect(Object.keys(store.file.templates)).toEqual(['b'])
    expect(store.usesOf('b').rules).toEqual([0])
    expect(store.yaml.value).toContain('<<: *template-b')
  })
})

describe('store server state', () => {
  it('is only dirty on a server file, and clean again after saving', () => {
    const store = createStore()
    store.load('rules: []\n', 'local.yml')
    store.addRule()
    expect(store.serverFile.value).toBeNull()
    expect(store.dirty.value).toBe(false)
    store.markSaved('rules.yml', '')
    expect(store.dirty.value).toBe(true)
    store.markSaved()
    expect(store.dirty.value).toBe(false)
    store.addRule()
    expect(store.dirty.value).toBe(true)
  })

  it('leaves server mode when a local file is loaded', () => {
    const store = createStore()
    store.markSaved('rules.yml')
    store.load('rules: []\n', 'local.yml')
    expect(store.serverFile.value).toBeNull()
  })
})

describe('store documents', () => {
  const ONE =
    'rules:\n  - name: one\n    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]\n    when: {type: bool, field: seen}\n'

  it('applies text without leaving the server document', () => {
    const store = createStore()
    store.markSaved('rules.yml', '', '# raw\nrules: []\n')
    store.applyText(ONE)
    expect(store.serverFile.value).toBe('rules.yml')
    expect(store.serverRaw.value).toBe('# raw\nrules: []\n')
    expect(store.dirty.value).toBe(true)
    expect(() => store.applyText('rules: [')).toThrow(/\S/)
    expect(store.file.rules).toHaveLength(1)
  })

  it('opens a file beside the server document and brings the edits back', () => {
    const store = createStore()
    store.load(ONE, 'server.yml')
    store.markSaved('server.yml')
    store.addRule()
    expect(store.dirty.value).toBe(true)

    store.openDocument('rules: []\n', 'mine.yml')
    expect(store.serverFile.value).toBeNull()
    expect(store.file.rules).toHaveLength(0)
    expect(store.documents.map((item) => item.name)).toEqual(['mine.yml'])
    expect(store.canUndo.value).toBe(false)
    expect(store.isEdited('server')).toBe(true)

    store.switchTo('server')
    expect(store.serverFile.value).toBe('server.yml')
    expect(store.file.rules).toHaveLength(2)
    expect(store.dirty.value).toBe(true)
    expect(store.fileName.value).toBe('server.yml')
  })

  it('keeps the edits of an ad-hoc document and tells edited ones', () => {
    const store = createStore()
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
    expect(store.fileName.value).toBe('rules.yml')
  })

  it('does not change anything when the file to open is broken', () => {
    const store = createStore()
    store.load(ONE, 'a.yml')
    expect(() => store.openDocument('rules: [', 'bad.yml')).toThrow(/\S/)
    expect(store.documents).toHaveLength(0)
    expect(store.file.rules).toHaveLength(1)
  })
})
