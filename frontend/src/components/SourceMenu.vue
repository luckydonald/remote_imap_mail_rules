<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from '@/model/store/rules'
import { SERVER } from '@/model/store/rules'

const store = useStore()
const menu = ref<HTMLDetailsElement | null>(null)

interface Entry {
  id: string
  label: string
  edited: boolean
}

function serverLabel(): string {
  const backend = store.backend
  if (backend?.kind === 'database') return '🗄️ Database'
  return `📄 ${backend?.name ?? store.serverFile ?? ''}`
}

function memoryLabel(name: string | null, index: number, short = false): string {
  if (short || (name === null && store.documents.length < 2)) return '🕳️ In Memory'
  return `🕳️ In Memory · ${name ?? `new ${index + 1}`}`
}

/** What is being edited, and so what Save would write; shown in every view. */
const current = computed(() => {
  if (store.serverFile !== null) return serverLabel()
  const index = store.documents.findIndex((item) => item.id === store.memoryId)
  const document = store.documents[index]
  return memoryLabel(document?.name ?? null, index, document === undefined)
})

const liveId = computed(() => (store.serverFile !== null ? SERVER : store.memoryId))

/** The server's rules first, then every ad-hoc file of the session. */
const entries = computed<Entry[]>(() => {
  const list: Entry[] = []
  if (store.backend !== null && (store.serverFile !== null || store.serverStash))
    list.push({ id: SERVER, label: serverLabel(), edited: store.isEdited(SERVER) })
  store.documents.forEach((document, index) =>
    list.push({
      id: document.id,
      label: memoryLabel(document.name, index, false),
      edited: store.isEdited(document.id),
    }),
  )
  return list
})

function choose(id: string): void {
  store.switchTo(id)
  if (menu.value) menu.value.open = false
}
</script>

<template>
  <details v-if="entries.length > 1" ref="menu" class="file source-menu">
    <summary title="What is edited, and where Save writes it">{{ current }}</summary>
    <ul>
      <li v-for="entry in entries" :key="entry.id">
        <button
          type="button"
          class="ghost"
          :class="{ current: entry.id === liveId }"
          :aria-current="entry.id === liveId"
          @click="choose(entry.id)"
        >
          {{ entry.label }}{{ entry.edited ? ' ●' : '' }}
        </button>
      </li>
    </ul>
  </details>
  <span v-else class="file source-menu" title="What is edited, and where Save writes it">{{
    current
  }}</span>
</template>
