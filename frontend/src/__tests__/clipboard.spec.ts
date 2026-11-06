import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { parseExpressionText } from '@/model/store/clipboard'
import { useStore } from '@/model/store'
import { stringifyExpression } from '@/model/yaml-io'
import type { Expression } from '@/model/types'

const nested: Expression = {
  type: 'all',
  conditions: [
    { type: 'not', condition: { type: 'bool', field: 'seen' } },
    { type: 'address', field: 'from', operator: 'equals', part: 'domain', value: 'example.org' },
    { type: 'template', ref: 'news', variables: { sender: { var: 'who' } } },
  ],
}

function fakeClipboard(text = '') {
  const clipboard: {
    text: string
    writeText: Mock<(value: string) => Promise<void>>
    readText: Mock<() => Promise<string>>
  } = {
    text,
    writeText: vi.fn<(value: string) => Promise<void>>(
      async (value) => void (clipboard.text = value),
    ),
    readText: vi.fn<() => Promise<string>>(async () => clipboard.text),
  }
  vi.stubGlobal('navigator', { clipboard })
  return clipboard
}

beforeEach(() => {
  // The settings are kept in localStorage, so a test must not see the one before.
  localStorage.clear()
  setActivePinia(createPinia())
  vi.unstubAllGlobals()
})

describe('parseExpressionText', () => {
  it('round trips a nested block with a template use and a variable', () => {
    expect(parseExpressionText(stringifyExpression(nested))).toEqual(nested)
  })

  it('rejects text that is no rule block', () => {
    expect(parseExpressionText('just some words')).toBeNull()
    expect(parseExpressionText('type: nonsense')).toBeNull()
    expect(parseExpressionText('type: text\nfield: nonsense')).toBeNull()
    expect(parseExpressionText('a: [')).toBeNull()
    expect(parseExpressionText('')).toBeNull()
  })
})

describe('clipboard in the central store', () => {
  it('keeps a copy of the cut block and writes its YAML', async () => {
    const clipboard = fakeClipboard()
    const store = useStore()
    const block: Expression = { type: 'bool', field: 'seen' }
    await store.cutBlock(block)
    block.type = 'bool'
    expect(store.clipboardBlock).toEqual({ type: 'bool', field: 'seen' })
    expect(parseExpressionText(clipboard.text)).toEqual(store.clipboardBlock)
  })

  it('writes nothing with the setting off, but still pastes the cut block', async () => {
    const clipboard = fakeClipboard('type: bool\nfield: flagged\n')
    const store = useStore()
    store.copyCut = 'off'
    store.readPaste = 'off'
    await store.cutBlock({ type: 'bool', field: 'seen' })
    expect(clipboard.writeText).not.toHaveBeenCalled()
    expect(clipboard.readText).not.toHaveBeenCalled()
    expect(await store.readBlock()).toEqual({ type: 'bool', field: 'seen' })
  })

  it('prefers a rule block from the clipboard, else falls back to the cut block', async () => {
    const clipboard = fakeClipboard('type: bool\nfield: flagged\n')
    const store = useStore()
    expect(await store.readBlock()).toEqual({ type: 'bool', field: 'flagged' })
    await store.cutBlock({ type: 'bool', field: 'seen' })
    clipboard.text = 'not a block'
    expect(await store.readBlock()).toEqual({ type: 'bool', field: 'seen' })
    clipboard.readText.mockRejectedValueOnce(new Error('denied'))
    expect(await store.readBlock()).toEqual({ type: 'bool', field: 'seen' })
  })

  it('has nothing to paste without a block and without a readable clipboard', async () => {
    fakeClipboard('')
    const store = useStore()
    store.readPaste = 'off'
    expect(store.canPaste).toBe(false)
    expect(await store.readBlock()).toBeNull()
  })
})
