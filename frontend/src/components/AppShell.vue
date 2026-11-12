<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AccountsView from './AccountsView.vue'
import ActionLogView from './ActionLogView.vue'
import GitView from './GitView.vue'
import MailLogin from './MailLogin.vue'
import MailView from './MailView.vue'
import RuleEditor from './RuleEditor.vue'
import RuleList from './RuleList.vue'
import SampleErrorView from './SampleErrorView.vue'
import SettingsView from './SettingsView.vue'
import SourceMenu from './SourceMenu.vue'
import TemplatesView from './TemplatesView.vue'
import YamlPanel from './YamlPanel.vue'
import { fetchConfig, fetchRules, saveRules, SaveError } from '@/model/api'
import { logout } from '@/model/mail-api'
import { clearAll } from '@/model/offline/db'
import { setOnline } from '@/model/online'
import ConfirmLogout from './ConfirmLogout.vue'
import OnlineOnly from './OnlineOnly.vue'
import OfflineBanner from './OfflineBanner.vue'
import UpdateBanner from './UpdateBanner.vue'
import { useStore } from '@/model/store'
import { locationOfView, viewOfRoute } from '@/router'

const store = useStore()

const fileInput = ref<HTMLInputElement | null>(null)
const notice = ref('')
const dragging = ref(false)
const saving = ref(false)
const online = ref(false)
const loginRequired = ref(false)
const askLogout = ref(false)
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
    const current = store.view
    if (
      view.kind !== current.kind ||
      (view.kind === 'rule' && current.kind === 'rule' && view.index !== current.index)
    )
      store.view = view
  },
  { immediate: true },
)
watch(
  () => store.view,
  (view) => {
    if (screen.value !== 'rules') return
    const target = router.resolve(locationOfView(view))
    if (target.fullPath !== route.fullPath) void router.push(target)
  },
  { deep: true },
)
/** The Rules link returns to the view that was open. */
const rulesLink = computed(() => locationOfView(store.view))

/** Loads the server's rules file when a server answers; without one the editor stays file based. */
async function connect(): Promise<void> {
  const config = await fetchConfig()
  if (config === 'login') {
    loginRequired.value = true
    online.value = false
    store.active = false
    return
  }
  if (!config) return
  loginRequired.value = false
  online.value = true
  store.active = true
  store.actionsEnabled = config.actions_enabled === true
  // Offline from the start: known before the background round runs, which then cleans nothing up.
  if (config.offline) setOnline(false)
  store.startOffline()
  const label = config.file_name ?? 'the database'
  store.backend = { kind: config.source, name: config.file_name }
  if (config.offline) {
    notice.value = 'The server cannot be reached, showing the cached mails.'
    return
  }
  try {
    const text = await fetchRules()
    if (text !== null) store.load(text, label)
    else store.fileName = label
    store.markSaved(label, undefined, text ?? undefined)
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

/** The Log out button: unsent offline changes are asked about first. */
function logOutClicked(): void {
  if (store.queued.length > 0) askLogout.value = true
  else void logOut(true)
}

async function sendThenLogOut(): Promise<void> {
  await store.sendQueue()
  if (store.queued.length > 0) return
  askLogout.value = false
  await logOut(true)
}

/** `wipe` forgets the offline cache too; an expired session keeps it, the queue is sent after the next login. */
async function logOut(wipe = false): Promise<void> {
  askLogout.value = false
  try {
    await logout()
  } catch {
    // Offline: the session cookie stays, but the screens are locked all the same.
  }
  if (wipe) await clearAll()
  online.value = false
  store.active = false
  store.clear()
  loginRequired.value = true
  void router.push(locationOfView(store.view))
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const text = store.yaml
    await saveRules(text)
    store.markSaved(undefined, text, text)
    notice.value = `Saved ${store.serverFile}.`
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
    store.openDocument(await file.text(), file.name)
    notice.value = `Opened ${file.name} in memory${store.backend ? ', it is not written to the server' : ''}.`
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
  const url = URL.createObjectURL(new Blob([store.yaml], { type: 'text/yaml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = store.fileName
  link.click()
  URL.revokeObjectURL(url)
}

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(store.yaml)
    notice.value = 'YAML copied.'
  } catch {
    notice.value = 'Copying is blocked by the browser, use the YAML view.'
  }
}

function reset(): void {
  store.openDocument('rules: []\n')
  store.view = { kind: 'yaml' }
}

function onKey(event: KeyboardEvent): void {
  if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'z') return
  const target = event.target as HTMLElement
  if (['INPUT', 'TEXTAREA'].includes(target.tagName)) return
  event.preventDefault()
  if (event.shiftKey) store.redo()
  else store.undo()
}

/** Asks the browser to confirm closing the tab or window while a document has unsaved edits. */
function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (!store.anyEdited) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('beforeunload', onBeforeUnload)
  void connect()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<template>
  <div class="app" @dragover="onDragOver" @dragleave="dragging = false" @drop="onDrop">
    <header class="topbar">
      <h1>Mail rules</h1>
      <SourceMenu />
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
        <RouterLink :to="{ name: 'git' }" class="ghost" :class="{ current: screen === 'git' }"
          >Git</RouterLink
        >
        <RouterLink :to="{ name: 'mail' }" class="ghost" :class="{ current: screen === 'mail' }"
          >Mail</RouterLink
        >
        <RouterLink :to="{ name: 'log' }" class="ghost" :class="{ current: screen === 'log' }"
          >Log</RouterLink
        >
        <RouterLink
          :to="{ name: 'settings' }"
          class="ghost"
          :class="{ current: screen === 'settings' }"
          >Settings</RouterLink
        >
        <button type="button" class="ghost" @click="logOutClicked">Log out</button>
      </nav>
      <button
        v-if="online && screen === 'rules'"
        type="button"
        class="ghost mail-toggle"
        :class="{ current: store.panelOpen }"
        title="Show a mail beside the rule to fill conditions from it"
        @click="store.panelOpen = !store.panelOpen"
      >
        Example mail
      </button>
      <template v-if="screen !== 'mail' && screen !== 'log' && screen !== 'settings'">
        <button type="button" @click="fileInput?.click()">Open…</button>
        <input ref="fileInput" type="file" accept=".yml,.yaml,text/yaml" hidden @change="onPick" />
        <button type="button" class="ghost" @click="reset">New</button>
        <button
          type="button"
          class="ghost"
          :disabled="!store.canUndo"
          title="Undo"
          @click="store.undo()"
        >
          ↶
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!store.canRedo"
          title="Redo"
          @click="store.redo()"
        >
          ↷
        </button>
        <button type="button" class="ghost" @click="copy">Copy YAML</button>
        <button type="button" @click="download">Download</button>
        <button
          v-if="store.serverFile !== null"
          type="button"
          class="save"
          :disabled="saving || !store.dirty || store.problems.length > 0 || !store.isOnline"
          :title="
            store.isOnline ? `Write ${store.serverFile} on the server` : 'Not available offline'
          "
          @click="save"
        >
          Save to {{ store.backend?.kind === 'database' ? 'Database' : store.serverFile
          }}{{ store.dirty ? ' ●' : '' }}
        </button>
        <span
          v-if="store.problems.length > 0"
          class="badge error"
          @click="store.view = { kind: 'yaml' }"
          >{{ store.problems.length }} problems</span
        >
        <span v-else class="badge ok">valid</span>
      </template>
    </header>
    <p v-if="notice" class="notice" @click="notice = ''">{{ notice }}</p>
    <UpdateBanner />
    <OfflineBanner />
    <ConfirmLogout
      v-if="askLogout"
      :count="store.queued.length"
      @send="sendThenLogOut"
      @logout="logOut(true)"
      @cancel="askLogout = false"
    />
    <MailLogin v-if="loginRequired" @logged-in="loggedIn" />
    <SampleErrorView v-else-if="screen === 'sample-error'" />
    <MailView v-else-if="screen === 'mail'" @unauthorized="logOut()" />
    <OnlineOnly v-else-if="screen === 'log'">
      <ActionLogView @unauthorized="logOut()" />
    </OnlineOnly>
    <SettingsView v-else-if="screen === 'settings'" />
    <OnlineOnly v-else-if="screen === 'accounts'"><AccountsView /></OnlineOnly>
    <OnlineOnly v-else-if="screen === 'git'"><GitView /></OnlineOnly>
    <div v-else class="body" :class="{ 'with-mail': online && store.panelOpen }">
      <RuleList />
      <main>
        <RuleEditor
          v-if="store.view.kind === 'rule' && store.file.rules[store.view.index]"
          :key="store.view.index"
          :rule="store.file.rules[store.view.index]!"
          :index="store.view.index"
        />
        <TemplatesView v-else-if="store.view.kind === 'templates'" />
        <YamlPanel v-else />
      </main>
      <aside v-if="online && store.panelOpen" class="mail-panel">
        <MailView compact @unauthorized="logOut()" @close="store.panelOpen = false" />
      </aside>
    </div>
    <div v-if="dragging" class="drop">Drop a rules file to open it</div>
  </div>
</template>
