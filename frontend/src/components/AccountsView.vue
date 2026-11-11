<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  AccountError,
  checkAccount,
  createAccount,
  deleteAccount,
  updateAccount,
  type Account,
  type AccountCheckResult,
  type AccountInput,
} from '@/model/accounts-api'
import { useStore } from '@/model/store'

// The list is the mail browser's, so the account picker there follows every change made here.
const store = useStore()
const message = ref('')
const loading = ref(true)
/** `null` is closed, `'new'` adds, an id edits. */
const editing = ref<string | 'new' | null>(null)
const confirming = ref<string | null>(null)

const emptyForm = (): AccountInput => ({
  id: '',
  name: '',
  host: '',
  port: 993,
  ssl: true,
  username: '',
  password: '',
  page_size: 50,
  poll_interval: 60,
})
const form = ref<AccountInput>(emptyForm())
/** The last login check of the form; a failed one on Save keeps the form open and offers `Save anyway`. */
const check = ref<AccountCheckResult | null>(null)
const checking = ref(false)

function describe(error: unknown): string {
  return error instanceof AccountError
    ? error.messages.join('; ')
    : error instanceof Error
      ? error.message
      : String(error)
}

async function load(renamed?: { from: string; to: string }): Promise<void> {
  try {
    await store.refreshAccounts(renamed)
  } catch (error) {
    message.value = `Could not load the accounts: ${describe(error)}`
  } finally {
    loading.value = false
  }
}

/** A time as the user's locale shows it, `never` for none. */
function when(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : 'never'
}

function add(): void {
  form.value = emptyForm()
  editing.value = 'new'
  check.value = null
  message.value = ''
}

function edit(account: Account): void {
  form.value = {
    id: account.id,
    name: account.name,
    host: account.host,
    port: account.port,
    ssl: account.ssl,
    username: account.username,
    password: '',
    page_size: account.page_size,
    poll_interval: account.poll_interval,
  }
  editing.value = account.id
  check.value = null
  message.value = ''
}

const UUID_PATTERN = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'

/** Whether the login depends on something the form changed; renaming an account needs no network call. */
function loginChanged(): boolean {
  const old = store.accounts.find((a) => a.id === editing.value)
  if (!old) return true
  const f = form.value
  return (
    f.host !== old.host ||
    f.port !== old.port ||
    f.ssl !== old.ssl ||
    f.username !== old.username ||
    f.password !== ''
  )
}

async function runCheck(): Promise<boolean> {
  checking.value = true
  check.value = null
  try {
    check.value = await checkAccount({
      ...form.value,
      id: editing.value === 'new' ? '' : (editing.value ?? ''),
    })
  } catch (error) {
    check.value = { ok: false, kind: 'unreachable', message: describe(error) }
  } finally {
    checking.value = false
  }
  return check.value.ok
}

/** Save checks the login first; a failure stops here and `Save anyway` calls `save` directly. */
async function submit(): Promise<void> {
  if (loginChanged() && !(await runCheck())) return
  await save()
}

async function save(): Promise<void> {
  try {
    let renamed: { from: string; to: string } | undefined
    if (editing.value === 'new') await createAccount(form.value)
    else if (editing.value) {
      const from = editing.value
      const updated = await updateAccount(from, form.value)
      if (updated.id !== from) renamed = { from, to: updated.id }
    }
    editing.value = null
    check.value = null
    message.value = 'Saved.'
    await load(renamed)
  } catch (error) {
    message.value = `Not saved: ${describe(error)}`
  }
}

async function remove(id: string): Promise<void> {
  try {
    await deleteAccount(id)
    confirming.value = null
    message.value = 'Deleted.'
    await load()
  } catch (error) {
    confirming.value = null
    message.value = `Not deleted: ${describe(error)}`
  }
}

onMounted(() => void load())
</script>

<template>
  <section class="accounts">
    <header class="row">
      <h2>Accounts</h2>
      <span class="spacer" />
      <button type="button" class="add" @click="add">Add account</button>
    </header>
    <p v-if="message" class="message" @click="message = ''">{{ message }}</p>
    <p v-if="!loading && store.accounts.length === 0" class="hint">No accounts yet.</p>
    <article v-for="account in store.accounts" :key="account.id" class="account">
      <header class="row">
        <strong>{{ account.name }}</strong>
        <span class="mono">{{ account.username }}@{{ account.host }}:{{ account.port }}</span>
        <span
          v-if="account.env_differs.length > 0"
          class="badge error"
          :title="`Differs from the environment: ${account.env_differs.join(', ')}`"
          >differs from env: {{ account.env_differs.join(', ') }}</span
        >
        <span
          v-if="account.needs_check"
          class="badge error needs-check"
          title="The mail server rejected the login and it has not worked since."
          >⚠ Please check</span
        >
        <span class="spacer" />
        <button type="button" class="ghost" @click="edit(account)">Edit</button>
        <template v-if="confirming === account.id">
          <button type="button" class="danger" @click="remove(account.id)">Really delete</button>
          <button type="button" class="ghost" @click="confirming = null">Cancel</button>
        </template>
        <button v-else type="button" class="ghost danger" @click="confirming = account.id">
          Delete
        </button>
      </header>
      <p class="hint mono">{{ account.id }}</p>
      <dl class="login-history muted">
        <dt>Credentials set</dt>
        <dd>{{ when(account.auth_updated_at) }}</dd>
        <dt>Last login worked</dt>
        <dd>{{ when(account.auth_ok_at) }}</dd>
        <dt>Last login rejected</dt>
        <dd>
          {{ when(account.auth_failed_at) }}
          <template v-if="account.auth_fail_count > 0">
            ({{ account.auth_fail_count }}× since the credentials were set)
          </template>
        </dd>
        <template v-if="account.auth_last_error">
          <dt>Server said</dt>
          <dd class="mono">{{ account.auth_last_error }}</dd>
        </template>
      </dl>
    </article>
    <form v-if="editing" class="account-form" @submit.prevent="submit">
      <h3>{{ editing === 'new' ? 'New account' : 'Edit account' }}</h3>
      <label
        >ID (UUID)
        <input
          v-model="form.id"
          name="id"
          class="mono"
          :pattern="UUID_PATTERN"
          :placeholder="editing === 'new' ? 'generated' : ''"
          title="The same id on two systems lets them share rules."
        />
      </label>
      <p v-if="editing !== 'new'" class="hint">
        Changing the id rewrites it in the rules (locations, move actions and conditions) too.
      </p>
      <label>Name <input v-model="form.name" name="name" required /></label>
      <label>Host <input v-model="form.host" name="host" required /></label>
      <label
        >Port
        <input v-model.number="form.port" name="port" type="number" min="1" max="65535" required
      /></label>
      <label class="check"><input v-model="form.ssl" name="ssl" type="checkbox" /> SSL</label>
      <label>Username <input v-model="form.username" name="username" required /></label>
      <label
        >Password
        <input
          v-model="form.password"
          name="password"
          type="password"
          autocomplete="new-password"
          :required="editing === 'new'"
          :placeholder="editing === 'new' ? '' : 'unchanged'"
        />
      </label>
      <label
        >Page size <input v-model.number="form.page_size" name="page_size" type="number" min="1"
      /></label>
      <label
        >Poll interval (s)
        <input v-model.number="form.poll_interval" name="poll_interval" type="number" min="1"
      /></label>
      <p v-if="check" class="check-result" :class="check.ok ? 'ok' : 'error'" role="status">
        {{ check.ok ? '✓' : '✗' }} {{ check.message }}
      </p>
      <div class="row">
        <button type="submit" :disabled="checking">Save</button>
        <button type="button" class="test" :disabled="checking" @click="runCheck">
          {{ checking ? 'Testing…' : 'Test connection' }}
        </button>
        <button v-if="check && !check.ok" type="button" class="save-anyway" @click="save">
          Save anyway
        </button>
        <button type="button" class="ghost" @click="editing = null">Cancel</button>
      </div>
    </form>
  </section>
</template>
