<script setup lang="ts">
/** Stats of the server (needs it) and of what this browser caches (works offline). A snapshot, the reload button asks again. */
import { onMounted, ref } from 'vue'
import { fileSize, fullDate } from '@/model/mail-format'
import { cacheStats, type CacheStats } from '@/model/offline/stats'
import { fetchStats, type Stats } from '@/model/stats-api'
import { useOnline } from '@/model/online'
import OnlineOnly from './OnlineOnly.vue'

const { isOnline } = useOnline()
const server = ref<Stats | null>(null)
const serverError = ref('')
const browser = ref<CacheStats | null>(null)
const loading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  serverError.value = ''
  try {
    browser.value = await cacheStats()
    if (isOnline.value) {
      try {
        server.value = await fetchStats()
      } catch (error) {
        serverError.value = error instanceof Error ? error.message : String(error)
      }
    }
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<template>
  <main class="settings-view settings-stats">
    <h2>
      Stats
      <button
        type="button"
        class="ghost"
        :disabled="loading"
        aria-label="Reload stats"
        @click="reload"
      >
        ↻
      </button>
    </h2>
    <OnlineOnly>
      <section aria-labelledby="stats-server">
        <h3 id="stats-server">Server</h3>
        <p v-if="serverError" class="error">{{ serverError }}</p>
        <dl v-else-if="server">
          <dt>Database</dt>
          <dd>
            {{ server.database.dialect
            }}<template v-if="server.database.size_bytes !== null"
              >, {{ fileSize(server.database.size_bytes) }}</template
            >
          </dd>
          <dt>Data folder</dt>
          <dd>{{ fileSize(server.data_dir_bytes) }}</dd>
          <dt>Accounts</dt>
          <dd>{{ server.tables.accounts }}</dd>
          <dt>Rules</dt>
          <dd>{{ server.tables.rules }} (templates: {{ server.tables.templates }})</dd>
          <dt>MCP tokens</dt>
          <dd>{{ server.tables.mcp_tokens }}</dd>
          <dt>Log entries</dt>
          <dd>
            {{ server.tables.mail_events }}
            <template v-for="(count, kind) in server.tables.mail_events_by_kind" :key="kind">
              · {{ kind }}: {{ count }}
            </template>
          </dd>
          <dt>Log from</dt>
          <dd>
            {{ fullDate(server.first_event) || '–' }} to {{ fullDate(server.last_event) || '–' }}
          </dd>
          <dt>Watcher</dt>
          <dd>
            {{ server.watcher.enabled ? 'on' : 'off' }}, actions
            {{ server.watcher.actions_enabled ? 'on' : 'off' }},
            {{ server.watcher.folders }} folders, {{ server.watcher.jobs }} running
          </dd>
          <dt>Running since</dt>
          <dd>{{ fullDate(server.started_at) }}</dd>
          <dt>Release</dt>
          <dd>{{ server.release }}</dd>
        </dl>
        <p v-else class="hint">Loading…</p>
      </section>
    </OnlineOnly>
    <section aria-labelledby="stats-browser">
      <h3 id="stats-browser">This browser</h3>
      <dl v-if="browser">
        <template v-for="store in browser.stores" :key="store.store">
          <dt>{{ store.store }}</dt>
          <dd>{{ store.records }} records, about {{ fileSize(store.bytes) }}</dd>
        </template>
        <dt>Mails kept for</dt>
        <dd>
          <template v-if="Object.keys(browser.reasons).length === 0">–</template>
          <template v-for="(count, reason) in browser.reasons" :key="reason"
            >{{ reason }}: {{ count }}&nbsp;</template
          >
        </dd>
        <dt>Storage used</dt>
        <dd>
          <template v-if="browser.usage !== null"
            >{{ fileSize(browser.usage) }} of {{ fileSize(browser.quota) }}</template
          >
          <template v-else>unknown</template>
        </dd>
        <dt>App files</dt>
        <dd>{{ browser.workerEntries }} cached</dd>
        <dt>Preferences</dt>
        <dd>{{ fileSize(browser.localStorageBytes) }}</dd>
      </dl>
      <p v-else class="hint">Loading…</p>
    </section>
  </main>
</template>
