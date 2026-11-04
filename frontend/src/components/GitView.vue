<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { describeError } from '@/model/http'
import {
  fetchGitState,
  generateSshKey,
  runGitAction,
  saveGitSettings,
  type GitAction,
  type GitSettingsInput,
  type GitState,
} from '@/model/git-api'

const state = ref<GitState | null>(null)
const form = ref<GitSettingsInput | null>(null)
/** Typed token; empty keeps the stored one. */
const token = ref('')
const message = ref('')
const busy = ref(false)
const showFiles = ref(false)

const status = computed(() => state.value?.status ?? null)
const canCommit = computed(() => !!status.value?.initialized && status.value.changed.length > 0)
const canPush = computed(
  () => !!status.value?.initialized && !!status.value.last_commit && !!form.value?.remote_url,
)

/** Takes a new server state; the form is only replaced when asked, so unsaved edits survive an action. */
function adopt(next: GitState, resetForm = false): void {
  state.value = next
  if (!resetForm && form.value) return
  form.value = { ...next.settings, token: null }
}

async function load(): Promise<void> {
  try {
    adopt(await fetchGitState(), true)
  } catch (error) {
    message.value = `Could not load the git state: ${describeError(error)}`
  }
}

async function save(): Promise<void> {
  if (!form.value) return
  busy.value = true
  try {
    adopt(
      await saveGitSettings({ ...form.value, token: token.value === '' ? null : token.value }),
      true,
    )
    token.value = ''
    message.value = 'Saved.'
  } catch (error) {
    message.value = `Not saved: ${describeError(error)}`
  } finally {
    busy.value = false
  }
}

async function run(action: GitAction): Promise<void> {
  busy.value = true
  try {
    const { done, state: next } = await runGitAction(action)
    adopt(next)
    message.value = action === 'commit' && !done ? 'Nothing to commit.' : 'Done.'
  } catch (error) {
    message.value = describeError(error)
    await load()
  } finally {
    busy.value = false
  }
}

async function newKey(): Promise<void> {
  busy.value = true
  try {
    adopt(await generateSshKey())
  } catch (error) {
    message.value = describeError(error)
  } finally {
    busy.value = false
  }
}

async function clearToken(): Promise<void> {
  if (!form.value) return
  form.value.token = ''
  await save()
}

async function copyKey(): Promise<void> {
  if (state.value?.public_key) await navigator.clipboard.writeText(state.value.public_key)
}

function toggleAutoCommit(): void {
  // Pushing automatically needs committing automatically.
  if (form.value && !form.value.auto_commit) form.value.auto_push = false
}

onMounted(() => void load())
</script>

<template>
  <section class="git">
    <header class="row">
      <h2>Git</h2>
      <span v-if="state" class="hint mono">{{ state.directory }}</span>
    </header>
    <p v-if="message" class="message" @click="message = ''">{{ message }}</p>
    <template v-if="state && status && form">
      <p v-if="!status.git_available" class="badge error">
        The git binary is missing on the server.
      </p>
      <div class="row status">
        <span v-if="!status.initialized" class="badge error">not initialised</span>
        <template v-else>
          <span class="badge ok">{{ status.branch }}</span>
          <span v-if="status.changed.length === 0" class="badge ok">clean</span>
          <button v-else type="button" class="badge error link" @click="showFiles = !showFiles">
            {{ status.changed.length }} uncommitted
          </button>
          <span v-if="status.ahead > 0" class="badge error">{{ status.ahead }} to push</span>
          <span v-else-if="status.remote_configured && status.last_commit" class="badge ok"
            >pushed</span
          >
          <span v-if="status.behind > 0" class="badge error">{{ status.behind }} behind</span>
          <span v-if="status.last_commit" class="hint mono">{{ status.last_commit }}</span>
        </template>
      </div>
      <ul v-if="showFiles && status.changed.length > 0" class="files mono">
        <li v-for="file in status.changed" :key="file">{{ file }}</li>
      </ul>
      <p v-if="state.last_error" class="badge error last-error">{{ state.last_error }}</p>

      <div class="row actions">
        <button
          v-if="!status.initialized"
          type="button"
          name="init"
          :disabled="busy || !status.git_available"
          @click="run('init')"
        >
          Initialise
        </button>
        <button
          type="button"
          name="commit"
          :disabled="busy || !canCommit"
          :title="canCommit ? '' : 'Nothing to commit'"
          @click="run('commit')"
        >
          Commit now
        </button>
        <button
          type="button"
          name="push"
          :disabled="busy || !canPush"
          :title="canPush ? '' : 'Needs a commit and a remote URL'"
          @click="run('push')"
        >
          Push now
        </button>
        <button
          type="button"
          class="ghost"
          name="fetch"
          :disabled="busy || !form.remote_url"
          @click="run('fetch')"
        >
          Check remote
        </button>
      </div>

      <form class="git-form" @submit.prevent="save">
        <label class="check">
          <input v-model="form.enabled" name="enabled" type="checkbox" /> Enabled
        </label>
        <label class="check">
          <input
            v-model="form.auto_commit"
            name="auto_commit"
            type="checkbox"
            @change="toggleAutoCommit"
          />
          Commit automatically after each save
        </label>
        <label class="check">
          <input
            v-model="form.auto_push"
            name="auto_push"
            type="checkbox"
            :disabled="!form.auto_commit"
          />
          Push automatically after each commit
        </label>
        <label>Remote URL <input v-model="form.remote_url" name="remote_url" /></label>
        <label>Branch <input v-model="form.branch" name="branch" required /></label>
        <label>Author name <input v-model="form.author_name" name="author_name" required /></label>
        <label
          >Author email <input v-model="form.author_email" name="author_email" required
        /></label>
        <label
          >Credentials
          <select v-model="form.auth_method" name="auth_method">
            <option value="none">None (local path or public remote)</option>
            <option value="https">HTTPS token</option>
            <option value="ssh">SSH deploy key</option>
          </select>
        </label>
        <template v-if="form.auth_method === 'https'">
          <label>Username <input v-model="form.username" name="username" /></label>
          <label
            >Token
            <input
              v-model="token"
              name="token"
              type="password"
              autocomplete="new-password"
              :placeholder="state.settings.has_token ? 'token saved, type to replace' : ''"
            />
          </label>
          <button
            v-if="state.settings.has_token"
            type="button"
            class="ghost danger"
            @click="clearToken"
          >
            Remove token
          </button>
        </template>
        <div v-if="form.auth_method === 'ssh'" class="ssh">
          <p class="hint">
            Add this public key as a deploy key with write access on the remote, and use an SSH URL.
          </p>
          <pre v-if="state.public_key" class="mono key">{{ state.public_key }}</pre>
          <div class="row">
            <button v-if="state.public_key" type="button" class="ghost" @click="copyKey">
              Copy
            </button>
            <button type="button" class="ghost" name="ssh-key" :disabled="busy" @click="newKey">
              {{ state.public_key ? 'Regenerate key' : 'Generate key' }}
            </button>
          </div>
        </div>
        <div class="row">
          <button type="submit" :disabled="busy">Save</button>
        </div>
      </form>
    </template>
  </section>
</template>
