<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  AccountError,
  createAccount,
  deleteAccount,
  listAccounts,
  updateAccount,
  type Account,
  type AccountInput,
} from '@/model/accounts-api'

const accounts = ref<Account[]>([])
const message = ref('')
const loading = ref(true)
/** `null` is closed, `'new'` adds, an id edits. */
const editing = ref<string | 'new' | null>(null)
const confirming = ref<string | null>(null)

const emptyForm = (): AccountInput => ({
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

function describe(error: unknown): string {
  return error instanceof AccountError
    ? error.messages.join('; ')
    : error instanceof Error
      ? error.message
      : String(error)
}

async function load(): Promise<void> {
  try {
    accounts.value = await listAccounts()
  } catch (error) {
    message.value = `Could not load the accounts: ${describe(error)}`
  } finally {
    loading.value = false
  }
}

function add(): void {
  form.value = emptyForm()
  editing.value = 'new'
  message.value = ''
}

function edit(account: Account): void {
  form.value = {
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
  message.value = ''
}

async function submit(): Promise<void> {
  try {
    if (editing.value === 'new') await createAccount(form.value)
    else if (editing.value) await updateAccount(editing.value, form.value)
    editing.value = null
    message.value = 'Saved.'
    await load()
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
    <p v-if="!loading && accounts.length === 0" class="hint">No accounts yet.</p>
    <article v-for="account in accounts" :key="account.id" class="account">
      <header class="row">
        <strong>{{ account.name }}</strong>
        <span class="mono">{{ account.username }}@{{ account.host }}:{{ account.port }}</span>
        <span
          v-if="account.env_differs.length > 0"
          class="badge error"
          :title="`Differs from the environment: ${account.env_differs.join(', ')}`"
          >differs from env: {{ account.env_differs.join(', ') }}</span
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
    </article>
    <form v-if="editing" class="account-form" @submit.prevent="submit">
      <h3>{{ editing === 'new' ? 'New account' : 'Edit account' }}</h3>
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
      <div class="row">
        <button type="submit">Save</button>
        <button type="button" class="ghost" @click="editing = null">Cancel</button>
      </div>
    </form>
  </section>
</template>
