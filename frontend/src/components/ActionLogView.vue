<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { listAccounts, type Account } from '@/model/accounts-api'
import { ApiError, describeError } from '@/model/http'
import {
  EVENT_KINDS,
  fetchLog,
  fetchLogStatus,
  filtersOfQuery,
  NO_FILTERS,
  queryOfFilters,
  type LogEntry,
  type LogJob,
  type LogFilters,
  type LogStatus,
} from '@/model/log-api'
import { eventLabel, fullDate } from '@/model/mail-format'

const emit = defineEmits<{ unauthorized: [] }>()

const route = useRoute()
const router = useRouter()
const filters = reactive<LogFilters>({ ...NO_FILTERS, ...filtersOfQuery(route.query) })
const entries = ref<LogEntry[]>([])
const next = ref<string | null>(null)
const status = ref<LogStatus | null>(null)
const accounts = ref<Account[]>([])
const message = ref('')
const loading = ref(false)
/** Answers of an older request must not replace the ones of the newest. */
let requestId = 0
let timer: ReturnType<typeof setTimeout> | undefined
/** The working jobs change by the second, so the status is asked again while the screen is open. */
const STATUS_INTERVAL = 5000
let statusTimer: ReturnType<typeof setTimeout> | undefined

const accountNames = computed(() => new Map(accounts.value.map((a) => [a.id, a.name])))
const filtered = computed(() => JSON.stringify(filters) !== JSON.stringify(NO_FILTERS))

function fail(error: unknown, what: string): void {
  if (error instanceof ApiError && error.status === 401) emit('unauthorized')
  else message.value = `Could not load ${what}: ${describeError(error)}`
}

async function loadStatus(): Promise<void> {
  try {
    status.value = await fetchLogStatus()
  } catch (error) {
    fail(error, 'the status')
  }
}

function pollStatus(): void {
  statusTimer = setTimeout(async () => {
    await loadStatus()
    pollStatus()
  }, STATUS_INTERVAL)
}

/** Loads the first page, or the one after the last when `more`. */
async function load(more = false): Promise<void> {
  const id = ++requestId
  loading.value = true
  message.value = ''
  try {
    const page = await fetchLog(filters, more ? next.value : null)
    if (id !== requestId) return
    entries.value = more ? [...entries.value, ...page.items] : page.items
    next.value = page.next
  } catch (error) {
    if (id === requestId) fail(error, 'the log')
  } finally {
    if (id === requestId) loading.value = false
  }
}

async function refresh(): Promise<void> {
  await Promise.all([load(), loadStatus()])
}

function reset(): void {
  Object.assign(filters, NO_FILTERS, { kinds: [] })
}

// The filters live in the URL, so a view can be linked; typing waits a moment before it asks.
watch(
  filters,
  () => {
    void router.replace({ query: queryOfFilters(filters) })
    clearTimeout(timer)
    timer = setTimeout(() => void load(), 300)
  },
  { deep: true },
)

onMounted(async () => {
  void refresh()
  pollStatus()
  try {
    accounts.value = await listAccounts()
  } catch {
    // the names fall back to the ids
  }
})
onBeforeUnmount(() => {
  clearTimeout(timer)
  clearTimeout(statusTimer)
})

function jobLabel(job: LogJob): string {
  return job.kind === 'actions' ? 'Running rules on mail' : 'Checking folder'
}

function when(iso: string | null): string {
  if (iso !== null) return fullDate(iso)
  return 'never'
}

const runText = computed(() => {
  if (!status.value) return '…'
  if (!status.value.watcher_enabled) return 'The watcher is switched off'
  return status.value.last_run ? fullDate(status.value.last_run) : 'not since the server started'
})

const nextText = computed(() => {
  const current = status.value
  if (!current) return '…'
  if (!current.watcher_enabled) return 'The watcher is switched off'
  if (current.next_run) {
    const when = fullDate(current.next_run)
    return current.push ? `${when} (and on server push)` : when
  }
  return current.push ? 'on change (server push)' : 'not scheduled yet'
})
</script>

<template>
  <section class="action-log">
    <header class="row">
      <h2>Action log</h2>
      <span class="spacer" />
      <button type="button" class="ghost" :disabled="loading" @click="refresh">Refresh</button>
    </header>
    <dl class="info" aria-label="Watcher status">
      <div>
        <dt>Watcher last ran</dt>
        <dd data-test="last-run">{{ runText }}</dd>
      </div>
      <div>
        <dt>Next scheduled run</dt>
        <dd data-test="next-run">{{ nextText }}</dd>
      </div>
      <div>
        <dt>Last change found</dt>
        <dd data-test="last-change">{{ status ? when(status.last_change) : '…' }}</dd>
      </div>
      <div>
        <dt>Last action ran</dt>
        <dd data-test="last-action">{{ status ? when(status.last_action) : '…' }}</dd>
      </div>
    </dl>
    <section class="jobs" aria-label="Working jobs">
      <h3>Working now</h3>
      <ul v-if="status && status.jobs.length > 0" data-test="jobs">
        <li
          v-for="job in status.jobs"
          :key="`${job.kind}|${job.account_id}|${job.folder}|${job.uid}`"
        >
          <span class="what">{{ jobLabel(job) }}</span>
          <RouterLink
            v-if="job.uid !== null"
            class="where"
            :to="{
              name: 'mail-message',
              params: { accountId: job.account_id, folder: job.folder, uid: job.uid },
            }"
          >
            {{ accountNames.get(job.account_id) ?? job.account_id }} · {{ job.folder }} ·
            {{ job.uid }}
          </RouterLink>
          <span v-else class="where">
            {{ accountNames.get(job.account_id) ?? job.account_id }} · {{ job.folder }}
          </span>
          <time :datetime="job.started_at">since {{ fullDate(job.started_at) }}</time>
        </li>
      </ul>
      <p v-else class="empty" data-test="no-jobs">
        {{ status ? 'Nothing is running right now.' : '…' }}
      </p>
    </section>
    <form class="filters" @submit.prevent="load()">
      <input v-model="filters.q" type="search" placeholder="Search" aria-label="Search" />
      <select v-model="filters.account_id" aria-label="Account">
        <option value="">All accounts</option>
        <option v-for="account in accounts" :key="account.id" :value="account.id">
          {{ account.name }}
        </option>
      </select>
      <input v-model="filters.folder" placeholder="Folder" aria-label="Folder" />
      <input v-model="filters.rule" placeholder="Rule" aria-label="Rule" />
      <label>From <input v-model="filters.since" type="datetime-local" aria-label="From" /></label>
      <label>To <input v-model="filters.until" type="datetime-local" aria-label="To" /></label>
      <fieldset class="kinds">
        <label v-for="item in EVENT_KINDS" :key="item.kind">
          <input v-model="filters.kinds" type="checkbox" :value="item.kind" />
          {{ item.label }}
        </label>
      </fieldset>
      <button v-if="filtered" type="button" class="ghost" @click="reset">Clear filters</button>
    </form>
    <p v-if="message" class="message error" @click="message = ''">{{ message }}</p>
    <ol class="entries">
      <li v-for="entry in entries" :key="entry.id" :class="entry.kind">
        <time :datetime="entry.created_at">{{ fullDate(entry.created_at) }}</time>
        <span class="what">{{ eventLabel(entry) }}</span>
        <RouterLink
          class="where"
          :to="{
            name: 'mail-message',
            params: { accountId: entry.account_id, folder: entry.folder, uid: entry.uid },
          }"
        >
          {{ accountNames.get(entry.account_id) ?? entry.account_id }} · {{ entry.folder }} ·
          {{ entry.uid }}
        </RouterLink>
      </li>
    </ol>
    <p v-if="!loading && entries.length === 0 && !message" class="hint">
      {{ filtered ? 'Nothing matches these filters.' : 'Nothing was logged yet.' }}
    </p>
    <button v-if="next" type="button" :disabled="loading" @click="load(true)">Load more…</button>
  </section>
</template>
