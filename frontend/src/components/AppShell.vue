<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AccountsView from './AccountsView.vue'
import MailLogin from './MailLogin.vue'
import MailView from './MailView.vue'
import RuleEditor from './RuleEditor.vue'
import RuleList from './RuleList.vue'
import TemplatesView from './TemplatesView.vue'
import YamlPanel from './YamlPanel.vue'
import { fetchConfig, fetchRules, saveRules, SaveError } from '@/model/api'
import { provideStore } from '@/model/context'
import { logout } from '@/model/mail-api'
import { useMailStore } from '@/model/mail-store'
import { createStore } from '@/model/store'
import { locationOfView, viewOfRoute } from '@/router'

const store = createStore()
provideStore(store)
const mail = useMailStore()

const fileInput = ref<HTMLInputElement | null>(null)
const notice = ref('')
const dragging = ref(false)
const saving = ref(false)
const online = ref(false)
const loginRequired = ref(false)
const route = useRoute()
const router = useRouter()
const screen = computed(() => route.meta.screen ?? 'rules')

// The route and the editor view follow each other: a link changes the view, and the store
// changes it itself when it adds, removes or moves a rule or loads a file.
watch(
  () => [route.name, route.params.index] as const,
  () => {
    const view = viewOfRoute(route.name, route.params)
    if (view === null) return
    const current = store.view.value
    if (
      view.kind !== current.kind ||
      (view.kind === 'rule' && current.kind === 'rule' && view.index !== current.index)
    )
      store.view.value = view
  },
  { immediate: true },
)
watch(
  store.view,
  (view) => {
    if (screen.value !== 'rules') return
    const target = router.resolve(locationOfView(view))
    if (target.fullPath !== route.fullPath) void router.push(target)
  },
  { deep: true },
)
/** The Rules link returns to the view that was open. */
const rulesLink = computed(() => locationOfView(store.view.value))

/** Loads the server's rules file when a server answers; without one the editor stays file based. */
async function connect(): Promise<void> {
  const config = await fetchConfig()
  if (config === 'login') {
    loginRequired.value = true
    online.value = false
    mail.active = false
    return
  }
  if (!config) return
  loginRequired.value = false
  online.value = true
  mail.active = true
  const label = config.file_name ?? 'the database'
  try {
    const text = await fetchRules()
    if (text !== null) store.load(text, label)
    else store.fileName.value = label
    store.markSaved(label)
    notice.value =
      text !== null
        ? `Loaded ${label} from the server.`
        : `${label} has no rules yet, saving creates them.`
  } catch (error) {
    notice.value = `Could not load the rules from the server: ${error instanceof Error ? error.message : String(error)}`
  }
}

async function loggedIn(): Promise<void> {
  notice.value = ''
  await connect()
}

async function logOut(): Promise<void> {
  await logout()
  online.value = false
  mail.active = false
  mail.clear()
  loginRequired.value = true
  void router.push(locationOfView(store.view.value))
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const text = store.yaml.value
    await saveRules(text)
    store.markSaved(undefined, text)
    notice.value = `Saved ${store.serverFile.value}.`
  } catch (error) {
    notice.value =
      error instanceof SaveError
        ? `Not saved: ${error.messages.join('; ')}`
        : `Not saved: ${error instanceof Error ? error.message : String(error)}`
  } finally {
    saving.value = false
  }
}

async function openFile(file: File): Promise<void> {
  try {
    store.load(await file.text(), file.name)
    notice.value = `Opened ${file.name}.`
  } catch (error) {
    notice.value = `Could not open ${file.name}: ${error instanceof Error ? error.message : String(error)}`
  }
}

function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void openFile(file)
  input.value = ''
}

function onDrop(event: DragEvent): void {
  event.preventDefault()
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) void openFile(file)
}

function onDragOver(event: DragEvent): void {
  event.preventDefault()
  dragging.value = true
}

function download(): void {
  const url = URL.createObjectURL(new Blob([store.yaml.value], { type: 'text/yaml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = store.fileName.value
  link.click()
  URL.revokeObjectURL(url)
}

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(store.yaml.value)
    notice.value = 'YAML copied.'
  } catch {
    notice.value = 'Copying is blocked by the browser, use the YAML view.'
  }
}

function reset(): void {
  store.load('rules: []\n')
  store.view.value = { kind: 'yaml' }
}

function onKey(event: KeyboardEvent): void {
  if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'z') return
  const target = event.target as HTMLElement
  if (['INPUT', 'TEXTAREA'].includes(target.tagName)) return
  event.preventDefault()
  if (event.shiftKey) store.redo()
  else store.undo()
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  void connect()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="app" @dragover="onDragOver" @dragleave="dragging = false" @drop="onDrop">
    <header class="topbar">
      <h1>Mail rules</h1>
      <span class="file">{{ store.fileName.value }}</span>
      <span class="spacer" />
      <nav v-if="online" class="screens" aria-label="Screens">
        <RouterLink :to="rulesLink" class="ghost" :class="{ current: screen === 'rules' }">
          Rules
        </RouterLink>
        <RouterLink
          :to="{ name: 'accounts' }"
          class="ghost"
          :class="{ current: screen === 'accounts' }"
          >Accounts</RouterLink
        >
        <RouterLink :to="{ name: 'mail' }" class="ghost" :class="{ current: screen === 'mail' }"
          >Mail</RouterLink
        >
        <button type="button" class="ghost" @click="logOut">Log out</button>
      </nav>
      <button
        v-if="online && screen === 'rules'"
        type="button"
        class="ghost mail-toggle"
        :class="{ current: mail.panelOpen }"
        title="Show a mail beside the rule to fill conditions from it"
        @click="mail.panelOpen = !mail.panelOpen"
      >
        Example mail
      </button>
      <template v-if="screen !== 'mail'">
        <button type="button" @click="fileInput?.click()">Open…</button>
        <input ref="fileInput" type="file" accept=".yml,.yaml,text/yaml" hidden @change="onPick" />
        <button type="button" class="ghost" @click="reset">New</button>
        <button
          type="button"
          class="ghost"
          :disabled="!store.canUndo.value"
          title="Undo"
          @click="store.undo()"
        >
          ↶
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!store.canRedo.value"
          title="Redo"
          @click="store.redo()"
        >
          ↷
        </button>
        <button type="button" class="ghost" @click="copy">Copy YAML</button>
        <button type="button" @click="download">Download</button>
        <button
          v-if="store.serverFile.value !== null"
          type="button"
          class="save"
          :disabled="saving || !store.dirty.value || store.problems.value.length > 0"
          :title="`Write ${store.serverFile.value} on the server`"
          @click="save"
        >
          Save{{ store.dirty.value ? ' ●' : '' }}
        </button>
        <span
          v-if="store.problems.value.length > 0"
          class="badge error"
          @click="store.view.value = { kind: 'yaml' }"
          >{{ store.problems.value.length }} problems</span
        >
        <span v-else class="badge ok">valid</span>
      </template>
    </header>
    <p v-if="notice" class="notice" @click="notice = ''">{{ notice }}</p>
    <MailLogin v-if="loginRequired" @logged-in="loggedIn" />
    <MailView v-else-if="screen === 'mail'" @unauthorized="logOut" />
    <AccountsView v-else-if="screen === 'accounts'" />
    <div v-else class="body" :class="{ 'with-mail': online && mail.panelOpen }">
      <RuleList />
      <main>
        <RuleEditor
          v-if="store.view.value.kind === 'rule' && store.file.rules[store.view.value.index]"
          :key="store.view.value.index"
          :rule="store.file.rules[store.view.value.index]!"
          :index="store.view.value.index"
        />
        <TemplatesView v-else-if="store.view.value.kind === 'templates'" />
        <YamlPanel v-else />
      </main>
      <aside v-if="online && mail.panelOpen" class="mail-panel">
        <MailView compact @unauthorized="logOut" @close="mail.panelOpen = false" />
      </aside>
    </div>
    <div v-if="dragging" class="drop">Drop a rules file to open it</div>
  </div>
</template>
