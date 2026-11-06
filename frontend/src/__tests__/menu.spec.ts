import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useStore } from '@/model/store'

describe('menus in the central store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('closes the open menu when another one opens', () => {
    const menus = useStore()
    menus.openMenu('move')
    menus.openMenu('rule')
    expect(menus.isMenuOpen('move')).toBe(false)
    expect(menus.isMenuOpen('rule')).toBe(true)
  })

  it('toggles the open menu closed', () => {
    const menus = useStore()
    menus.toggleMenu('rule')
    expect(menus.isMenuOpen('rule')).toBe(true)
    menus.toggleMenu('rule')
    expect(menus.openMenuId).toBeNull()
  })

  it('leaves a different open menu alone when closing by id', () => {
    const menus = useStore()
    menus.openMenu('rule')
    menus.closeMenu('move')
    expect(menus.isMenuOpen('rule')).toBe(true)
    menus.closeMenu()
    expect(menus.openMenuId).toBeNull()
  })
})
