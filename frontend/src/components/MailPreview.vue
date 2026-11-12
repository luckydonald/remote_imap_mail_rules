<script setup lang="ts">
import { addressList, fullDate } from '@/model/mail-format'
import type { Detail } from '@/model/mail-api'

/** A short copy of the open mail (subject, sender, recipients, date) for dialogs that cover it. */
defineProps<{ detail: Detail }>()
</script>

<template>
  <section class="mail-preview" aria-label="Current mail">
    <strong class="subject">{{ detail.subject || '(no subject)' }}</strong>
    <dl>
      <dt>From</dt>
      <dd>{{ addressList([detail.sender]) }}</dd>
      <template v-if="detail.to.length">
        <dt>To</dt>
        <dd>{{ addressList(detail.to) }}</dd>
      </template>
      <dt>Date</dt>
      <dd>{{ fullDate(detail.date) }}</dd>
    </dl>
  </section>
</template>

<style scoped>
.mail-preview {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  margin-bottom: 0.6rem;
  min-width: 0;
}
.subject {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0 0.6rem;
  margin: 0.2rem 0 0;
  font-size: 0.85em;
  color: var(--muted);
}
dt {
  font-weight: 600;
}
dd {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
