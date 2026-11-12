<script setup lang="ts">
import { eventLabel, fullDate } from '@/model/mail-format'
import type { MailEvent } from '@/model/mail-api'

defineProps<{ events: MailEvent[]; offline?: boolean }>()
</script>

<template>
  <p v-if="offline" class="hint mail-log-offline">Offline, the log is not available.</p>
  <details v-else-if="events.length" class="mail-log" open>
    <summary>Log</summary>
    <ol>
      <li v-for="event in events" :key="event.id" :class="event.kind">
        <time :datetime="event.created_at">{{ fullDate(event.created_at) }}</time>
        <span class="what">{{ eventLabel(event) }}</span>
      </li>
    </ol>
  </details>
</template>
