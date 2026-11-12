<script setup lang="ts">
import { ref } from 'vue'
import QueueOverlay from './QueueOverlay.vue'
import { useStore } from '@/model/store'

const store = useStore()
const showQueue = ref(false)
</script>

<template>
  <div
    v-if="store.active && (!store.isOnline || store.queued.length > 0 || store.queueNotice)"
    class="offline-banner"
  >
    <span v-if="!store.isOnline" class="state">Offline, showing cached mails.</span>
    <button
      v-if="store.queued.length > 0"
      type="button"
      class="ghost queue-count"
      title="Show the queued changes"
      @click="showQueue = true"
    >
      {{ store.queued.length }}
    </button>
    <span v-if="store.queued.length > 0" class="hint">
      {{ store.queued.length === 1 ? 'change waits' : 'changes wait' }} to be sent.
    </span>
    <span v-if="store.queueNotice" class="notice-text" @click="store.queueNotice = ''">
      {{ store.queueNotice }}
    </span>
    <QueueOverlay v-if="showQueue" @close="showQueue = false" />
  </div>
</template>
