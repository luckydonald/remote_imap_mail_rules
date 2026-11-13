<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { autoReadDue, reachedEnd, visibleBottom, wantsAutoRead } from '@/model/auto-read'
import { addressList, fileSize, frameDocument, fullDate } from '@/model/mail-format'
import { useStore } from '@/model/store'
import type { BodyMode } from '@/model/store/prefs'
import ButtonSpinner from './ButtonSpinner.vue'
import MailAddCondition from './MailAddCondition.vue'
import MailLog from './MailLog.vue'
import MailMoveMenu from './MailMoveMenu.vue'
import MailRuleMenu from './MailRuleMenu.vue'
import MailSpinner from './MailSpinner.vue'
import SegmentedToggle from './SegmentedToggle.vue'

const props = defineProps<{ compact?: boolean }>()
const store = useStore()

const endMarker = ref<HTMLElement | null>(null)
const frame = ref<HTMLIFrameElement | null>(null)
let observer: ResizeObserver | null = null

/** The mode to show: the setting, or the other one when the mail has only that part. */
const mode = computed<BodyMode>(() => {
  const detail = store.detail
  if (!detail) return store.bodyMode
  if (store.bodyMode === 'html' && !detail.html && detail.text) return 'text'
  if (store.bodyMode === 'text' && !detail.text && detail.html) return 'html'
  return store.bodyMode
})
const modes = computed(() => [
  { value: 'text' as const, label: 'Text', disabled: !store.detail?.text },
  { value: 'html' as const, label: 'HTML', disabled: !store.detail?.html },
])
const showHtml = computed(() => mode.value === 'html' && !!store.detail?.html)

/** Grows the iframe to its content, the sandbox allows this because it keeps the origin but runs no scripts. */
function fit(): void {
  const body = frame.value?.contentDocument?.body
  if (frame.value && body) frame.value.style.height = `${body.scrollHeight}px`
  void nextTick(checkAutoRead)
}

/** Follows the content while images and fonts arrive, so the page scrolls as one and the frame never has a scrollbar of its own. */
function track(): void {
  observer?.disconnect()
  observer = null
  frameLoaded = true
  fit()
  const body = frame.value?.contentDocument?.body
  if (body && typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(fit)
    observer.observe(body)
  }
}

// The page (desktop) or the message column (narrow) scrolls; scroll events do not bubble, so listen in the capture phase of the window.
onMounted(() => window.addEventListener('scroll', checkAutoRead, { capture: true, passive: true }))
onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('scroll', checkAutoRead, { capture: true })
})

watch(
  () => [store.detail?.uid, showHtml.value] as const,
  () => void nextTick(fit),
)

// Automatic read (the admin's `auto_read` setting): decided once per opening, so `Mark unread` afterwards stays. Only the full screen does it.
let waitingUid: number | null = null
let frameLoaded = false

watch(
  () => store.detail?.uid,
  (uid) => {
    frameLoaded = false
    waitingUid = null
    const detail = store.detail
    if (props.compact || uid === undefined || !detail) return
    if (wantsAutoRead(store.autoRead, detail.seen, store.actionsEnabled)) waitingUid = uid
    void nextTick(checkAutoRead)
  },
  { immediate: true },
)

watch(showHtml, () => {
  frameLoaded = false
})

/** Marks the waiting mail read when the setting says so: when opened, or once the end of the mail is in view (the HTML frame has to be sized first). */
function checkAutoRead(): void {
  const detail = store.detail
  if (detail === null || waitingUid !== detail.uid) return
  const ready = !showHtml.value || frameLoaded
  const marker = endMarker.value
  const atEnd =
    ready && marker !== null && reachedEnd(marker.getBoundingClientRect().bottom, visibleBottom(marker))
  if (!autoReadDue(store.autoRead, atEnd)) return
  waitingUid = null
  void store.setSeen(true)
}

const remote = computed(() => store.detail?.remote_images_allowed ?? false)
const unreadLabel = computed(() => (store.detail?.seen ? 'Mark unread' : 'Mark read'))
</script>

<template>
  <article class="mail-message" aria-label="Message">
    <header class="pane-head">
      <button type="button" class="ghost back" @click="store.back()">‹ Messages</button>
      <div
        v-if="!compact && store.detail"
        class="toolbar"
        role="toolbar"
        aria-label="Message actions"
      >
        <button
          type="button"
          class="ghost toggle-seen"
          :disabled="!store.actionsEnabled || store.mailActionBusy !== null"
          :aria-busy="store.mailActionBusy === 'seen'"
          :title="
            store.actionsEnabled
              ? unreadLabel
              : 'Changing flags needs ACTIONS_ENABLED=true on the server.'
          "
          @click="store.setSeen(!store.detail.seen)"
        >
          <ButtonSpinner v-if="store.mailActionBusy === 'seen'" />{{ unreadLabel }}
        </button>
        <MailMoveMenu />
        <MailRuleMenu v-if="store.context" :context="store.context" />
        <SegmentedToggle v-model="store.bodyMode" :options="modes" label="Show the mail as" />
      </div>
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
      <details :key="store.detail.uid" class="all-headers">
        <summary>All headers ({{ store.detail.headers.length }})</summary>
        <dl>
          <template v-for="(header, index) in store.detail.headers" :key="index">
            <dt>{{ header.name }}</dt>
            <dd>{{ header.value }}</dd>
          </template>
        </dl>
      </details>
      <MailAddCondition v-if="compact && store.context" :context="store.context" />
      <ul v-if="store.detail.attachments.some((item) => !item.inline)" class="attachments">
        <li v-for="item in store.detail.attachments.filter((a) => !a.inline)" :key="item.part">
          <a :href="item.url" :download="item.filename ?? undefined">
            📎 {{ item.filename ?? `part ${item.part}` }}
            <span class="muted">{{ fileSize(item.size) }}</span>
          </a>
        </li>
      </ul>
      <details v-if="showHtml && store.detail.blocked_images.length" class="blocked-images">
        <summary>Blocked images ({{ store.detail.blocked_images.length }})</summary>
        <ul>
          <li v-for="url in store.detail.blocked_images" :key="url">
            <a :href="url" target="_blank" rel="noreferrer noopener">{{ url }}</a>
          </li>
        </ul>
        <button
          type="button"
          class="load-remote"
          :disabled="!store.isOnline"
          :title="store.isOnline ? undefined : 'Not available offline'"
          @click="store.allow({ remoteImages: true })"
        >
          Load remote images
        </button>
      </details>
      <p v-if="showHtml && store.detail.broken_embeds.length" class="hint broken-embeds">
        {{ store.detail.broken_embeds.length }} embedded image(s) are missing from this mail.
      </p>
      <p v-if="showHtml && store.detail.styles_blocked" class="hint styles-blocked">
        The styles of this mail are not shown.
        <button
          type="button"
          class="ghost load-styles"
          :disabled="!store.isOnline"
          :title="store.isOnline ? undefined : 'Not available offline'"
          @click="store.allow({ styles: true })"
        >
          Load styles
        </button>
      </p>
      <iframe
        v-if="showHtml && store.detail.html"
        ref="frame"
        class="body-frame"
        title="Message body"
        sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        :srcdoc="frameDocument(store.detail.html, remote)"
        @load="track"
      />
      <pre v-else-if="store.detail.text" class="body-text">{{ store.detail.text }}</pre>
      <p v-else class="hint">This message has no text.</p>
      <MailLog :events="store.events" :offline="store.eventsOffline" />
      <div ref="endMarker" class="end-marker" aria-hidden="true"></div>
    </template>
  </article>
</template>
