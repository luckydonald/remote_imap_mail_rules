<script setup lang="ts">
/** The bearer tokens of the MCP server: created here, shown once, revoked here. */
import { computed, onMounted, ref } from 'vue'
import { describeError } from '@/model/http'
import {
  createMcpToken,
  fetchMcpScopes,
  fetchMcpTokens,
  groupScopes,
  revokeMcpToken,
  scopeAction,
  type McpScopes,
  type McpToken,
} from '@/model/mcp-tokens-api'

const tokens = ref<McpToken[]>([])
const available = ref<McpScopes>({ scopes: [], presets: {} })
const name = ref('')
const chosen = ref<string[]>([])
const created = ref<string | null>(null)
const error = ref('')
const copied = ref(false)
const confirming = ref<string | null>(null)

const groups = computed(() => groupScopes(available.value.scopes))
const presetNames: Record<string, string> = {
  read_only: 'Read only',
  rules_editor: 'Rules editor',
  everything: 'Everything',
}

async function load(): Promise<void> {
  try {
    ;[tokens.value, available.value] = await Promise.all([fetchMcpTokens(), fetchMcpScopes()])
    error.value = ''
  } catch (e) {
    error.value = describeError(e)
  }
}

async function create(): Promise<void> {
  error.value = ''
  try {
    const result = await createMcpToken(name.value.trim(), chosen.value)
    created.value = result.token
    copied.value = false
    name.value = ''
    chosen.value = []
    tokens.value = await fetchMcpTokens()
  } catch (e) {
    error.value = describeError(e)
  }
}

async function revoke(id: string): Promise<void> {
  confirming.value = null
  try {
    await revokeMcpToken(id)
    tokens.value = await fetchMcpTokens()
  } catch (e) {
    error.value = describeError(e)
  }
}

async function copy(): Promise<void> {
  if (created.value === null) return
  try {
    await navigator.clipboard.writeText(created.value)
    copied.value = true
  } catch {
    copied.value = false
  }
}

function formatTime(value: string | null): string {
  return value === null ? 'never' : new Date(value).toLocaleString()
}

onMounted(load)
</script>

<template>
  <section class="mcp-tokens">
    <h3>Tokens</h3>
    <p class="hint">
      An MCP client (Claude Code, ...) connects to <code>/mcp</code> with
      <code>Authorization: Bearer &lt;token&gt;</code>. A token only gets the tools of its scopes.
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div v-if="created" class="new-token" role="status">
      <strong>Copy the token now, it is not shown again.</strong>
      <code class="token-value">{{ created }}</code>
      <button type="button" @click="copy">{{ copied ? 'Copied' : 'Copy' }}</button>
      <button type="button" @click="created = null">Done</button>
    </div>

    <ul v-if="tokens.length" class="token-list">
      <li v-for="token in tokens" :key="token.id" :class="{ revoked: token.revoked_at }">
        <div>
          <strong>{{ token.name }}</strong> <code>{{ token.prefix }}…</code>
          <span v-if="token.revoked_at" class="badge">revoked</span>
        </div>
        <div class="hint">
          {{ token.scopes.join(', ') }}<br />
          created {{ formatTime(token.created_at) }}, last used {{ formatTime(token.last_used_at) }}
        </div>
        <template v-if="!token.revoked_at">
          <button v-if="confirming !== token.id" type="button" @click="confirming = token.id">
            Revoke
          </button>
          <template v-else>
            <button type="button" @click="revoke(token.id)">Revoke for good</button>
            <button type="button" @click="confirming = null">Cancel</button>
          </template>
        </template>
      </li>
    </ul>
    <p v-else class="hint">No tokens yet.</p>

    <form class="token-form" @submit.prevent="create">
      <h3>New token</h3>
      <label>
        Name
        <input v-model="name" type="text" required maxlength="255" placeholder="Claude Code" />
      </label>
      <div class="presets">
        Presets:
        <button
          v-for="(list, preset) in available.presets"
          :key="preset"
          type="button"
          @click="chosen = [...list]"
        >
          {{ presetNames[preset] ?? preset }}
        </button>
      </div>
      <fieldset v-for="group in groups" :key="group.resource">
        <legend>{{ group.resource }}</legend>
        <label v-for="scope in group.scopes" :key="scope" class="check">
          <input v-model="chosen" type="checkbox" :value="scope" />
          {{ scopeAction(scope) }}
        </label>
      </fieldset>
      <button type="submit" :disabled="!name.trim() || !chosen.length">Create token</button>
    </form>
  </section>
</template>

<style scoped>
.token-list {
  list-style: none;
  padding: 0;
}
.token-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  align-items: center;
  padding: 0.4rem 0;
}
.revoked {
  opacity: 0.6;
}
.token-value {
  display: block;
  overflow-wrap: anywhere;
  user-select: all;
}
.token-form fieldset {
  display: inline-block;
  margin: 0.25rem 0.5rem 0.25rem 0;
}
</style>
