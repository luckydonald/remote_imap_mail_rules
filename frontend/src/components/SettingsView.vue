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
  </main>
</template>
