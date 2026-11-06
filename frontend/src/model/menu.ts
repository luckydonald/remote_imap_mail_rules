/** How a dropdown menu uses the shared slot of the central store: a click outside closes the open one. */

import { computed, onBeforeUnmount, onMounted, type Ref, type WritableComputedRef } from 'vue'
import { useStore } from './store'

/**
 * The `open` flag of the menu `id`, backed by the shared slot, and closing it on a pointer press outside of `root`.
 * Call it in `setup`; the template and plain `open = false` assignments work as with a `ref`.
 */
export function useMenu(id: string, root: Ref<HTMLElement | null>): WritableComputedRef<boolean> {
  const store = useStore()
  const open = computed({
    get: () => store.isMenuOpen(id),
    set: (value: boolean) => (value ? store.openMenu(id) : store.closeMenu(id)),
  })

  function onPointerDown(event: Event): void {
    const target = event.target
    if (!store.isMenuOpen(id) || !(target instanceof Node)) return
    if (root.value?.contains(target)) return
    store.closeMenu(id)
  }

  /** On document level, since Safari does not focus a button on click and the key would never reach the menu. */
  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') store.closeMenu(id)
  }

  onMounted(() => {
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onPointerDown)
    document.removeEventListener('keydown', onKeyDown)
    store.closeMenu(id)
  })
  return open
}
