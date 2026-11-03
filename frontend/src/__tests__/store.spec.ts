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
