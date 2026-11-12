<script setup lang="ts">
/** `Move ▾`: the move targets the rules already use come first, `More …` opens the folder tree. */
import { computed, ref } from 'vue'
import { useMenu } from '@/model/menu'
import { useStore } from '@/model/store'
import ButtonSpinner from './ButtonSpinner.vue'
import MailFolderTree from './MailFolderTree.vue'

const store = useStore()

const root = ref<HTMLElement | null>(null)
const open = useMenu('move', root)
const tree = ref(false)

/** The folders that move actions of the rules point to, for this account and this folder's neighbours, most used first. */
const destinations = computed(() => {
  const counts = new Map<string, number>()
  for (const rule of store.file.rules) {
    for (const action of rule.actions ?? []) {
      if (action.type !== 'move' || typeof action.folder !== 'string') continue
      const account = action.account_id
      if (typeof account === 'string' && account !== '' && account !== store.accountId) continue
      if (typeof account === 'object' && account !== null) continue
      counts.set(action.folder, (counts.get(action.folder) ?? 0) + 1)
    }
  }
  return store.folders
    .filter((folder) => counts.has(folder.name) && folder.name !== store.folder)
    .sort((a, b) => (counts.get(b.name) ?? 0) - (counts.get(a.name) ?? 0))
})

const disabled = computed(() => !store.actionsEnabled)

async function move(name: string): Promise<void> {
  open.value = false
  tree.value = false
  await store.moveTo(name)
}
</script>

<template>
  <div ref="root" class="menu">
    <button
      type="button"
      class="ghost"
      aria-haspopup="menu"
      :aria-expanded="open"
      :disabled="disabled || store.mailActionBusy !== null"
      :aria-busy="store.mailActionBusy === 'move'"
      :title="disabled ? 'Moving needs ACTIONS_ENABLED=true on the server.' : 'Move this mail'"
      @click="open = !open"
    >
      <ButtonSpinner v-if="store.mailActionBusy === 'move'" />Move ▾
    </button>
    <div v-if="open" class="menu-pop" role="menu">
      <button
        v-for="folder in destinations"
        :key="folder.name"
        type="button"
        role="menuitem"
        @click="move(folder.name)"
      >
        {{ folder.display_name }}
      </button>
      <p v-if="destinations.length === 0" class="hint">No rule moves mails from here.</p>
      <hr />
      <button type="button" role="menuitem" class="more" @click="((tree = true), (open = false))">
        More …
      </button>
    </div>
    <!-- Out of the scrolling panes: Safari on an iPad clips a fixed dialog to the pane that holds it. -->
    <Teleport to="body">
      <div v-if="tree" class="modal-backdrop" @click.self="tree = false">
        <div class="modal" role="dialog" aria-modal="true" aria-label="Move to folder">
          <h3>Move to …</h3>
          <MailFolderTree :folders="store.folders" :current="store.folder" @select="move" />
          <footer><button type="button" class="ghost" @click="tree = false">Cancel</button></footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>
