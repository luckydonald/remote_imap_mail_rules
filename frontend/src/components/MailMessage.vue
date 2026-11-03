<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { addressList, fileSize, frameDocument, fullDate } from '@/model/mail-format'
import type { MailStore } from '@/model/mail-store'

const props = defineProps<{ store: MailStore }>()

const frame = ref<HTMLIFrameElement | null>(null)

/** Grows the iframe to its content, the sandbox allows this because it keeps the origin but runs no scripts. */
function fit(): void {
  const body = frame.value?.contentDocument?.documentElement
  if (frame.value && body) frame.value.style.height = `${body.scrollHeight}px`
}

watch(
  () => props.store.detail.value?.uid,
  () => void nextTick(fit),
)
</script>

<template>
  <article class="mail-message" aria-label="Message">
    <header class="pane-head">
      <button type="button" class="ghost back" @click="store.back()">‹ Messages</button>
    </header>
    <p v-if="store.error.value" class="message error" role="alert">{{ store.error.value }}</p>
    <p v-else-if="store.selectedUid.value === null" class="hint empty">No message selected.</p>
    <p v-else-if="!store.detail.value" class="hint">Loading…</p>
    <template v-else>
      <h2 class="subject">{{ store.detail.value.subject || '(no subject)' }}</h2>
      <dl class="meta">
        <dt>From</dt>
        <dd>{{ addressList([store.detail.value.sender]) }}</dd>
        <template v-if="store.detail.value.to.length">
          <dt>To</dt>
          <dd>{{ addressList(store.detail.value.to) }}</dd>
        </template>
        <template v-if="store.detail.value.cc.length">
          <dt>Cc</dt>
          <dd>{{ addressList(store.detail.value.cc) }}</dd>
        </template>
        <dt>Date</dt>
        <dd>{{ fullDate(store.detail.value.date) }}</dd>
      </dl>
      <ul v-if="store.detail.value.attachments.some((item) => !item.inline)" class="attachments">
        <li
          v-for="item in store.detail.value.attachments.filter((a) => !a.inline)"
          :key="item.part"
        >
          <a :href="item.url" :download="item.filename ?? undefined">
            📎 {{ item.filename ?? `part ${item.part}` }}
            <span class="muted">{{ fileSize(item.size) }}</span>
          </a>
        </li>
      </ul>
      <iframe
        v-if="store.detail.value.html"
        ref="frame"
        class="body-frame"
        title="Message body"
        sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        :srcdoc="frameDocument(store.detail.value.html)"
        @load="fit"
      />
      <pre v-else-if="store.detail.value.text" class="body-text">{{ store.detail.value.text }}</pre>
      <p v-else class="hint">This message has no text.</p>
    </template>
  </article>
</template>
