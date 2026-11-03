<script setup lang="ts">
import { personLabel, shortDate } from '@/model/mail-format'
import type { MailStore } from '@/model/mail-store'

defineProps<{ store: MailStore }>()
</script>

<template>
  <section class="mail-list" aria-label="Messages">
    <header class="pane-head">
      <button type="button" class="ghost back" @click="store.back()">‹ Folders</button>
      <strong>{{ store.currentFolder.value?.display_name ?? '' }}</strong>
      <span class="muted">{{ store.total.value }} messages</span>
    </header>
    <ul>
      <li v-for="mail in store.messages.value" :key="mail.uid">
        <button
          type="button"
          class="row-mail"
          :class="{ active: mail.uid === store.selectedUid.value, unread: !mail.seen }"
          @click="store.openMessage(mail.uid)"
        >
          <span class="dot" :title="mail.seen ? 'Read' : 'Unread'" />
          <span class="from">{{ personLabel(mail.sender) }}</span>
          <span class="when">{{ shortDate(mail.date) }}</span>
          <span class="subject">
            <span v-if="mail.flagged" aria-label="Flagged">🚩 </span
            >{{ mail.subject || '(no subject)' }}
            <span v-if="mail.has_attachments" aria-label="Has attachments">📎</span>
          </span>
        </button>
      </li>
    </ul>
    <p
      v-if="!store.loading.value && store.messages.value.length === 0 && !store.error.value"
      class="hint"
    >
      No messages.
    </p>
    <button
      v-if="store.hasMore.value"
      type="button"
      class="ghost more"
      :disabled="store.loading.value"
      @click="store.loadMore()"
    >
      {{ store.loading.value ? 'Loading…' : 'Load older messages' }}
    </button>
  </section>
</template>
