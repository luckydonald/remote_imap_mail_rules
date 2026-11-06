<script setup lang="ts">
import { useMailStore } from '@/model/store'

/** The mail the rule editor fills from; the × stops the filling, the mail stays open in the mail screens. */
const mail = useMailStore()
</script>

<template>
  <div v-if="mail.fillContext" class="mail-chip" :title="mail.fillContext.detail.subject">
    <span aria-hidden="true">✉️</span>
    <span class="subject">{{ mail.fillContext.detail.subject || '(no subject)' }}</span>
    <button
      type="button"
      class="ghost remove"
      aria-label="Do not fill from this mail"
      title="Do not fill from this mail"
      @click="mail.fillDetached = true"
    >
      ×
    </button>
  </div>
</template>
