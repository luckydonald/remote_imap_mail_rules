<script setup lang="ts">
/** The folders of an account as a tree like a file browser: triangles to open and close, arrow keys, a filter. */
import { computed, nextTick, ref } from 'vue'
import type { Folder } from '@/model/mail-api'
import { folderIcon } from '@/model/mail-format'

const props = defineProps<{ folders: Folder[]; current?: string | null }>()
const emit = defineEmits<{ select: [name: string] }>()

interface Node {
  key: string
  label: string
  depth: number
  /** `null` for a parent that is only a path of other folders, or not selectable. */
  folder: Folder | null
  children: Node[]
}

function segments(folder: Folder): string[] {
  return folder.delimiter ? folder.display_name.split(folder.delimiter) : [folder.display_name]
}

const roots = computed(() => {
  const top: Node[] = []
  const index = new Map<string, Node>()
  const sorted = [...props.folders].sort((a, b) => a.display_name.localeCompare(b.display_name))
  for (const folder of sorted) {
    const parts = segments(folder)
    let siblings = top
    let key = ''
    parts.forEach((part, depth) => {
      key = key === '' ? part : `${key}\u0000${part}`
      let node = index.get(key)
      if (!node) {
        node = { key, label: part, depth, folder: null, children: [] }
        index.set(key, node)
        siblings.push(node)
      }
      if (depth === parts.length - 1) node.folder = folder
      siblings = node.children
    })
  }
  return top
})

const closed = ref(new Set<string>())
const filter = ref('')
const focused = ref<string | null>(null)
const list = ref<HTMLElement | null>(null)

/** The nodes in display order; a filter shows the matches with their parents and ignores what is closed. */
const rows = computed(() => {
  const needle = filter.value.trim().toLowerCase()
  const out: { node: Node; open: boolean }[] = []
  const matches = (node: Node): boolean =>
    node.label.toLowerCase().includes(needle) || node.children.some(matches)
  const walk = (nodes: Node[]): void => {
    for (const node of nodes) {
      if (needle !== '' && !matches(node)) continue
      const open = needle !== '' || !closed.value.has(node.key)
      out.push({ node, open })
      if (open) walk(node.children)
    }
  }
  walk(roots.value)
  return out
})

function toggle(node: Node): void {
  const next = new Set(closed.value)
  if (next.has(node.key)) next.delete(node.key)
  else next.add(node.key)
  closed.value = next
}

function choose(node: Node): void {
  focused.value = node.key
  if (node.folder?.selectable && node.folder.name !== props.current)
    emit('select', node.folder.name)
  else if (node.children.length > 0) toggle(node)
}

async function focusRow(offset: number, from: string): Promise<void> {
  const at = rows.value.findIndex((row) => row.node.key === from)
  const target = rows.value[Math.min(rows.value.length - 1, Math.max(0, at + offset))]
  if (!target) return
  focused.value = target.node.key
  await nextTick()
  list.value?.querySelector<HTMLElement>('[tabindex="0"]')?.focus()
}

function onKey(event: KeyboardEvent, row: { node: Node; open: boolean }): void {
  const { node, open } = row
  if (event.key === 'ArrowDown') void focusRow(1, node.key)
  else if (event.key === 'ArrowUp') void focusRow(-1, node.key)
  else if (event.key === 'ArrowRight' && node.children.length > 0 && !open) toggle(node)
  else if (event.key === 'ArrowLeft' && node.children.length > 0 && open) toggle(node)
  else if (event.key === 'Enter' || event.key === ' ') choose(node)
  else return
  event.preventDefault()
}

const tabbable = computed(() => focused.value ?? rows.value[0]?.node.key ?? null)
</script>

<template>
  <div class="folder-tree">
    <input
      v-model="filter"
      type="search"
      placeholder="Filter folders"
      aria-label="Filter folders"
    />
    <ul ref="list" role="tree" aria-label="Folders">
      <li
        v-for="row in rows"
        :key="row.node.key"
        role="treeitem"
        :aria-expanded="row.node.children.length > 0 ? row.open : undefined"
        :aria-selected="row.node.folder?.name === current"
        :aria-disabled="!row.node.folder?.selectable || undefined"
        :tabindex="tabbable === row.node.key ? 0 : -1"
        :class="{
          current: row.node.folder?.name === current,
          disabled: !row.node.folder?.selectable,
        }"
        :style="{ paddingLeft: `${8 + row.node.depth * 18}px` }"
        @click="choose(row.node)"
        @keydown="onKey($event, row)"
      >
        <button
          v-if="row.node.children.length > 0"
          type="button"
          class="twisty"
          tabindex="-1"
          :aria-label="row.open ? 'Collapse' : 'Expand'"
          @click.stop="toggle(row.node)"
        >
          {{ row.open ? '▾' : '▸' }}
        </button>
        <span v-else class="twisty" />
        <span class="icon">{{ row.node.folder ? folderIcon(row.node.folder) : '📁' }}</span>
        <span class="label">{{ row.node.label }}</span>
      </li>
    </ul>
    <p v-if="rows.length === 0" class="hint">No folder matches.</p>
  </div>
</template>
