/** The shared slot of the dropdown menus: opening one closes the others. Part of the central store (`index.ts`), `useMenu` in `../menu.ts` is how a menu uses it. */

import { ref } from 'vue'

export function useMenus() {
  const openMenuId = ref<string | null>(null)

  function isMenuOpen(id: string): boolean {
    return openMenuId.value === id
  }

  function openMenu(id: string): void {
    openMenuId.value = id
  }

  /** Closes the menu `id`, or whichever is open without an id. A different open menu stays. */
  function closeMenu(id?: string): void {
    if (id === undefined || openMenuId.value === id) openMenuId.value = null
  }

  function toggleMenu(id: string): void {
    if (isMenuOpen(id)) closeMenu(id)
    else openMenu(id)
  }

  return { openMenuId, isMenuOpen, openMenu, closeMenu, toggleMenu }
}
