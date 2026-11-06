<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from '@/model/store'

const props = defineProps<{ template: string }>()
const store = useStore()

const entries = computed(() => store.pendingRenames[props.template] ?? [])
const collapsed = computed(() => store.renamesCollapsed[props.template] === true)
const counts = computed(() => entries.value.map((e) => store.countUsages(props.template, e.from)))
const chosen = computed(() =>
  counts.value.reduce((sum, count, i) => sum + (entries.value[i]?.include ? count : 0), 0),
)
const total = computed(() => counts.value.reduce((sum, count) => sum + count, 0))
const blocked = computed(() => entries.value.some((e) => e.include && e.to === ''))

function collapse(value: boolean): void {
  store.renamesCollapsed[props.template] = value
}

function apply(): void {
  store.renameVariables(props.template)
}
</script>

<template>
  <div v-if="entries.length > 0" class="rename">
    <button v-if="collapsed" type="button" class="rename-chip" @click="collapse(false)">
      ( ▾ rename <span class="count-badge">{{ total }}</span> )
    </button>
    <div v-else class="rename-box" role="alert">
      <button type="button" class="ghost close" title="Decide later" @click="collapse(true)">
        ✕
      </button>
      <h4>{{ entries.length === 1 ? 'Renaming variable' : 'Renaming variables' }}</h4>
      <p v-if="entries.length === 1">
        <code>{{ entries[0]?.from }}</code> → <code>{{ entries[0]?.to || '…' }}</code>
        <span class="count-badge">{{ counts[0] }}</span>
      </p>
      <ul v-else>
        <li v-for="(entry, i) in entries" :key="entry.from">
          <code>{{ entry.from }}</code> → <code>{{ entry.to || '…' }}</code>
          <span class="count-badge">{{ counts[i] }}</span>
          <button
            type="button"
            class="ghost check"
            :aria-pressed="entry.include"
            :title="entry.include ? 'Will be renamed' : 'Will not be renamed'"
            @click="entry.include = !entry.include"
          >
            <kbd>{{ entry.include ? '✓' : '·' }}</kbd>
          </button>
        </li>
      </ul>
      <p>
        Do you want to rename {{ entries.length === 1 ? '' : 'all ' }}
        <span class="count-badge">{{ chosen }}</span> usages?
      </p>
      <p class="buttons">
        <button type="button" :disabled="blocked" @click="apply">
          <kbd>Yes</kbd>
        </button>
        <button type="button" @click="collapse(true)"><kbd>No</kbd></button>
      </p>
    </div>
  </div>
</template>
