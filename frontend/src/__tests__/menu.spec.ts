import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useMenuStore } from '@/model/menu'

describe('useMenuStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('closes the open menu when another one opens', () => {
    const menus = useMenuStore()
    menus.open('move')
    menus.open('rule')
    expect(menus.isOpen('move')).toBe(false)
    expect(menus.isOpen('rule')).toBe(true)
  })

  it('toggles the open menu closed', () => {
    const menus = useMenuStore()
    menus.toggle('rule')
    expect(menus.isOpen('rule')).toBe(true)
    menus.toggle('rule')
    expect(menus.openId).toBeNull()
  })

  it('leaves a different open menu alone when closing by id', () => {
    const menus = useMenuStore()
    menus.open('rule')
    menus.close('move')
    expect(menus.isOpen('rule')).toBe(true)
    menus.close()
    expect(menus.openId).toBeNull()
  })
})
