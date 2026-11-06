<script setup lang="ts">
import { personLabel, shortDate } from '@/model/mail-format'
import type { MailStore } from '@/model/store'
import MailSpinner from './MailSpinner.vue'

defineProps<{ store: MailStore }>()
</script>

<template>
  <section class="mail-list" aria-label="Messages">
    <header class="pane-head">
      <button type="button" class="ghost back" @click="store.back()">‹ Folders</button>
      <strong>{{ store.currentFolder?.display_name ?? '' }}</strong>
      <span class="muted">{{ store.total }} messages</span>
      <button
        type="button"
        class="ghost reload"
        aria-label="Reload messages"
        title="Reload messages"
        :disabled="store.loading"
        @click="store.reloadMessages()"
      >
        ↻
      </button>
    </header>
    <ul>
      <li v-for="mail in store.messages" :key="mail.uid">
        <button
          type="button"
          class="row-mail"
          :class="{ active: mail.uid === store.selectedUid, unread: !mail.seen }"
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
    <p v-if="!store.loading && store.messages.length === 0 && !store.error" class="hint">
      No messages.
    </p>
    <MailSpinner v-if="store.loading" />
    <button v-else-if="store.hasMore" type="button" class="ghost more" @click="store.loadMore()">
      Load older messages
    </button>
  </section>
</template>
