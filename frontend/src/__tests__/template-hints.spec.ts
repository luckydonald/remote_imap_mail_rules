import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, setActivePinia } from 'pinia'
import { useStore } from '@/model/store'
import { shouldCheck } from '@/model/store/template-hints'

const storageKey = 'template-hints-checked'
const yaml = `
templates:
  read:
    type: template
    defaults: {}
    content: {type: bool, field: seen}
rules:
  - name: test
    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]
    when: {type: bool, field: seen}
`

let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  localStorage.removeItem(storageKey)
  pinia = createPinia()
  setActivePinia(pinia)
})

afterEach(() => {
  disposePinia(pinia)
  vi.useRealTimers()
  vi.restoreAllMocks()
})

it('checks on a different local calendar day', () => {
  const now = new Date(2026, 10, 19, 0, 5)
  expect(shouldCheck(null, now)).toBe(true)
  expect(shouldCheck('2026-11-18', now)).toBe(true)
  expect(shouldCheck('2026-11-19', now)).toBe(false)
})

it('refreshes on load and after markSaved, keeping intervening edits out of the snapshot', () => {
  const store = useStore()
  store.load(yaml)
  expect(store.hintAt(0, [])?.template).toBe('read')
  store.addRule()
  store.file.rules[1]!.when = { type: 'bool', field: 'seen' }
  expect(store.hintAt(1, [])).toBeUndefined()
  store.markSaved('rules.yml')
  expect(store.hintAt(1, [])?.template).toBe('read')
  expect(store.hintsFor('read')).toHaveLength(2)
})

it('drops a hint when its condition or the replacement template changes', () => {
  const store = useStore()
  store.load(yaml)
  const rule = store.file.rules[0]!
  rule.when = { type: 'bool', field: 'flagged' }
  expect(store.hintAt(0, [])).toBeUndefined()
  expect(store.templateHints).toHaveLength(0)
  store.undo()
  expect(store.hintAt(0, [])?.template).toBe('read')
  store.file.templates.read!.content = { type: 'bool', field: 'flagged' }
  expect(store.hintsFor('read')).toHaveLength(0)
})

it('refreshes when the tab becomes visible on a new day', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 10, 19, 23, 55))
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const store = useStore()
  expect(localStorage.getItem(storageKey)).toBe('2026-11-19')
  store.load(yaml)
  store.addRule()
  store.file.rules[1]!.when = { type: 'bool', field: 'seen' }
  document.dispatchEvent(new Event('visibilitychange'))
  expect(store.hintAt(1, [])).toBeUndefined()
  vi.setSystemTime(new Date(2026, 10, 20, 0, 5))
  document.dispatchEvent(new Event('visibilitychange'))
  expect(store.hintAt(1, [])?.template).toBe('read')
  expect(localStorage.getItem(storageKey)).toBe('2026-11-20')
})
