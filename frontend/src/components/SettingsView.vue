<script setup lang="ts">
/** How this browser shows mails. Kept in the browser (localStorage), nothing here is sent to the server. */
import { usePrefsStore } from '@/model/prefs'
import SegmentedToggle from './SegmentedToggle.vue'

const prefs = usePrefsStore()
</script>

<template>
  <main class="settings-view">
    <h2>Mail view</h2>
    <section>
      <h3>Show mails as</h3>
      <SegmentedToggle
        v-model="prefs.bodyMode"
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
        v-model="prefs.remoteImages"
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
        v-model="prefs.mailStyles"
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
    <h2>Rule editor</h2>
    <section>
      <h3>Copy cut blocks to the clipboard</h3>
      <SegmentedToggle
        v-model="prefs.copyCut"
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
        v-model="prefs.readPaste"
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
  </main>
</template>
