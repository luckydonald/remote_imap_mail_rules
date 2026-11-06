<script setup lang="ts">
import { useStore } from '@/model/store'

/** The mail the rule editor fills from; the × stops the filling, the mail stays open in the mail screens. */
const store = useStore()
</script>

<template>
  <div v-if="store.fillContext" class="mail-chip" :title="store.fillContext.detail.subject">
    <span aria-hidden="true">✉️</span>
    <span class="subject">{{ store.fillContext.detail.subject || '(no subject)' }}</span>
    <button
      type="button"
      class="ghost remove"
      aria-label="Do not fill from this mail"
      title="Do not fill from this mail"
      @click="store.fillDetached = true"
    >
      ×
    </button>
  </div>
</template>
