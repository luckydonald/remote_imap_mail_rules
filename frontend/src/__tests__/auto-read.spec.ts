import { describe, expect, it } from 'vitest'
import { autoReadDue, reachedEnd, wantsAutoRead } from '@/model/auto-read'

describe('reachedEnd', () => {
  it('counts a mail that fits in the view as at its end', () => {
    expect(reachedEnd(400, 700)).toBe(true)
  })

  it('is false while there is more below the view', () => {
    expect(reachedEnd(2000, 700)).toBe(false)
  })

  it('allows a few pixels of slack at the bottom', () => {
    expect(reachedEnd(707, 700)).toBe(true)
    expect(reachedEnd(720, 700)).toBe(false)
  })
})

describe('wantsAutoRead', () => {
  it('only waits for an unread mail when the setting is on and the server may write', () => {
    expect(wantsAutoRead('open', false, true)).toBe(true)
    expect(wantsAutoRead('scrolled', false, true)).toBe(true)
    expect(wantsAutoRead('off', false, true)).toBe(false)
    expect(wantsAutoRead('open', true, true)).toBe(false)
    expect(wantsAutoRead('open', false, false)).toBe(false)
  })
})

describe('autoReadDue', () => {
  it('reads at once when opened, regardless of the scroll position', () => {
    expect(autoReadDue('open', false)).toBe(true)
  })

  it('reads after scrolling only at the end', () => {
    expect(autoReadDue('scrolled', false)).toBe(false)
    expect(autoReadDue('scrolled', true)).toBe(true)
  })

  it('never reads when off', () => {
    expect(autoReadDue('off', true)).toBe(false)
  })
})
