/** Dropdown menus share one slot: opening one closes the others, and a click outside closes the open one. */

import { defineStore } from 'pinia'
import { computed, onBeforeUnmount, onMounted, ref, type Ref, type WritableComputedRef } from 'vue'

export const useMenuStore = defineStore('menu', () => {
  const openId = ref<string | null>(null)

  function isOpen(id: string): boolean {
    return openId.value === id
  }

  function open(id: string): void {
    openId.value = id
  }

  /** Closes the menu `id`, or whichever is open without an id. A different open menu stays. */
  function close(id?: string): void {
    if (id === undefined || openId.value === id) openId.value = null
  }

  function toggle(id: string): void {
    if (isOpen(id)) close(id)
    else open(id)
  }

  return { openId, isOpen, open, close, toggle }
})

/**
 * The `open` flag of the menu `id`, backed by the shared slot, and closing it on a pointer press outside of `root`.
 * Call it in `setup`; the template and plain `open = false` assignments work as with a `ref`.
 */
export function useMenu(id: string, root: Ref<HTMLElement | null>): WritableComputedRef<boolean> {
  const menus = useMenuStore()
  const open = computed({
    get: () => menus.isOpen(id),
    set: (value: boolean) => (value ? menus.open(id) : menus.close(id)),
  })

  function onPointerDown(event: Event): void {
    const target = event.target
    if (!menus.isOpen(id) || !(target instanceof Node)) return
    if (root.value?.contains(target)) return
    menus.close(id)
  }

  /** On document level, since Safari does not focus a button on click and the key would never reach the menu. */
  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') menus.close(id)
  }

  onMounted(() => {
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onPointerDown)
    document.removeEventListener('keydown', onKeyDown)
    menus.close(id)
  })
  return open
}
