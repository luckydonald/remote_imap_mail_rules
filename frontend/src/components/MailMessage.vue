<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { addressList, fileSize, frameDocument, fullDate } from '@/model/mail-format'
import type { MailStore } from '@/model/mail-store'
import MailAddCondition from './MailAddCondition.vue'
import MailSpinner from './MailSpinner.vue'

const props = defineProps<{ store: MailStore; compact?: boolean }>()

const frame = ref<HTMLIFrameElement | null>(null)

/** Grows the iframe to its content, the sandbox allows this because it keeps the origin but runs no scripts. */
function fit(): void {
  const body = frame.value?.contentDocument?.documentElement
  if (frame.value && body) frame.value.style.height = `${body.scrollHeight}px`
}

watch(
  () => props.store.detail?.uid,
  () => void nextTick(fit),
)
</script>

<template>
  <article class="mail-message" aria-label="Message">
    <header class="pane-head">
      <button type="button" class="ghost back" @click="store.back()">‹ Messages</button>
    </header>
    <p v-if="store.error" class="message error" role="alert">{{ store.error }}</p>
    <p v-else-if="store.selectedUid === null" class="hint empty">No message selected.</p>
    <MailSpinner v-else-if="!store.detail" />
    <template v-else>
      <h2 class="subject">{{ store.detail.subject || '(no subject)' }}</h2>
      <dl class="meta">
        <dt>From</dt>
        <dd>{{ addressList([store.detail.sender]) }}</dd>
        <template v-if="store.detail.to.length">
          <dt>To</dt>
          <dd>{{ addressList(store.detail.to) }}</dd>
        </template>
        <template v-if="store.detail.cc.length">
          <dt>Cc</dt>
          <dd>{{ addressList(store.detail.cc) }}</dd>
        </template>
        <dt>Date</dt>
        <dd>{{ fullDate(store.detail.date) }}</dd>
      </dl>
      <MailAddCondition v-if="compact && store.context" :context="store.context" />
      <ul v-if="store.detail.attachments.some((item) => !item.inline)" class="attachments">
        <li v-for="item in store.detail.attachments.filter((a) => !a.inline)" :key="item.part">
          <a :href="item.url" :download="item.filename ?? undefined">
            📎 {{ item.filename ?? `part ${item.part}` }}
            <span class="muted">{{ fileSize(item.size) }}</span>
          </a>
        </li>
      </ul>
      <iframe
        v-if="store.detail.html"
        ref="frame"
        class="body-frame"
        title="Message body"
        sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        :srcdoc="frameDocument(store.detail.html)"
        @load="fit"
      />
      <pre v-else-if="store.detail.text" class="body-text">{{ store.detail.text }}</pre>
      <p v-else class="hint">This message has no text.</p>
    </template>
  </article>
</template>
