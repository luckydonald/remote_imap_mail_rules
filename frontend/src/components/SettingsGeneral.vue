<script setup lang="ts">
/** How this browser shows mails. Kept in the browser (localStorage), nothing here is sent to the server. */
import { useStore } from '@/model/store'
import McpTokens from './McpTokens.vue'
import OnlineOnly from './OnlineOnly.vue'
import SegmentedToggle from './SegmentedToggle.vue'

const store = useStore()
</script>

<template>
  <main class="settings-view">
    <h2>Mail view</h2>
    <section>
      <h3>Show mails as</h3>
      <SegmentedToggle
        v-model="store.bodyMode"
        label="Show mails as"
        :options="[
          { value: 'html', label: 'HTML' },
          { value: 'text', label: 'Text' },
        ]"
      />
      <p class="hint">A mail with only one of the two is always shown as that one.</p>
    </section>
    <section>
      <h3>Remote images</h3>
      <SegmentedToggle
        v-model="store.remoteImages"
        label="Remote images"
        :options="[
          { value: 'block', label: 'Block' },
          { value: 'allow', label: 'Always load' },
        ]"
      />
      <p class="hint">
        A remote image tells the sender that and when you read the mail. Blocked images are listed
        above the mail, with a button to load them for that one mail.
      </p>
    </section>
    <section>
      <h3>Styles of mails</h3>
      <SegmentedToggle
        v-model="store.mailStyles"
        label="Styles of mails"
        :options="[
          { value: 'block', label: 'Block' },
          { value: 'allow', label: 'Always show' },
        ]"
      />
      <p class="hint">
        Allowed styles are filtered: no imports, no scripted values, nothing fixed over the page.
      </p>
    </section>
    <h2>Offline cache</h2>
    <OnlineOnly>
      <section>
        <h3>Mails kept for offline use</h3>
        <label class="check">
          <input v-model="store.cacheUnread" type="checkbox" />
          Unread mails of the folders I opened
        </label>
        <label class="check">
          <input v-model="store.cacheOpenedUnread" type="checkbox" />
          Mails I opened while they were unread
        </label>
        <label class="check">
          <input v-model="store.cacheInbox" type="checkbox" />
          The newest
          <input
            v-model.number="store.cacheInboxCount"
            type="number"
            min="0"
            step="10"
            aria-label="Number of newest INBOX mails to keep"
            :disabled="!store.cacheInbox"
          />
          INBOX mails of each account
        </label>
        <label class="check">
          Drop mails not viewed for
          <input
            v-model.number="store.cacheMaxAgeDays"
            type="number"
            min="0"
            aria-label="Days after which an unviewed mail leaves the cache"
          />
          days (0 keeps them)
        </label>
        <p class="hint">
          A mail leaves the cache once it is read, unless it is one of the newest INBOX mails, and
          after the days above without a visit. Attachments are never cached. These settings are
          kept on the server, so every browser has the same.
        </p>
      </section>
    </OnlineOnly>
    <h2>Rule editor</h2>
    <section>
      <h3>Copy cut blocks to the clipboard</h3>
      <SegmentedToggle
        v-model="store.copyCut"
        label="Copy cut blocks to the clipboard"
        :options="[
          { value: 'on', label: 'On' },
          { value: 'off', label: 'Off' },
        ]"
      />
      <p class="hint">
        A cut block is always kept in the editor. With this on its YAML also goes to the clipboard,
        which clipboard history managers may record.
      </p>
    </section>
    <section>
      <h3>Paste from the clipboard</h3>
      <SegmentedToggle
        v-model="store.readPaste"
        label="Paste from the clipboard"
        :options="[
          { value: 'on', label: 'On' },
          { value: 'off', label: 'Off' },
        ]"
      />
      <p class="hint">
        Paste tries the clipboard first and takes the last cut block when it holds no rule block.
        Browsers may ask for permission to read the clipboard.
      </p>
    </section>
    <h2>MCP server</h2>
    <OnlineOnly>
      <McpTokens />
    </OnlineOnly>
  </main>
</template>
