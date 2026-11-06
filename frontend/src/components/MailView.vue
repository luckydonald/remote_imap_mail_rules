<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MailFolders from './MailFolders.vue'
import MailList from './MailList.vue'
import MailMessage from './MailMessage.vue'
import { useMailStore, type Place } from '@/model/store'
import { locationOfMail, mailPlaceOfRoute } from '@/router'

const props = defineProps<{ compact?: boolean }>()
const emit = defineEmits<{ unauthorized: []; close: [] }>()

const store = useMailStore()

store.setUnauthorizedHandler(() => emit('unauthorized'))

// The full screen shows its place in the URL (`/mail/<account>/<folder>/<uid>`), the side panel of
// the rule editor does not. The URL wins when it names a place, else the URL takes the store's.
const route = useRoute()
const router = useRouter()
const routePlace = (): Place => mailPlaceOfRoute(route.params)
const storePlace = (): Place => ({
  accountId: store.accountId,
  folder: store.folder,
  uid: store.selectedUid,
})
const same = (a: Place, b: Place): boolean =>
  a.accountId === b.accountId && a.folder === b.folder && a.uid === b.uid

function showPlaceInUrl(): void {
  const place = storePlace()
  // Half chosen places (account known, folder still loading) would overwrite the URL asked for.
  if (
    props.compact ||
    route.meta.screen !== 'mail' ||
    place.accountId === null ||
    place.folder === null
  )
    return
  if (same(place, routePlace())) return
  const target = router.resolve(locationOfMail(place))
  // A URL without a folder is only an entry point, it is replaced instead of kept in the history.
  if (routePlace().folder === null) void router.replace(target)
  else void router.push(target)
}

function followUrl(): void {
  if (props.compact || route.meta.screen !== 'mail') return
  const place = routePlace()
  if (place.accountId === null) showPlaceInUrl()
  else if (!same(place, storePlace())) void store.goTo(place)
}

watch(() => [store.accountId, store.folder, store.selectedUid], showPlaceInUrl)
watch(() => route.fullPath, followUrl)

onMounted(async () => {
  await store.loadAccounts(props.compact ? undefined : routePlace())
  followUrl()
  showPlaceInUrl()
})
</script>

<template>
  <div class="mail-view" :class="{ compact }">
    <header v-if="compact" class="panel-head">
      <button type="button" class="ghost close-panel" @click="emit('close')">‹ Rules</button>
      <strong>Example mail</strong>
    </header>
    <div class="mail" :class="{ compact }" :data-pane="store.pane">
      <p v-if="store.error && !store.detail && store.selectedUid === null" class="message error">
        {{ store.error }}
      </p>
      <p
        v-if="store.accounts.length === 0 && !store.error && !store.foldersLoading"
        class="hint empty"
      >
        No accounts yet, add one on the Accounts screen.
      </p>
      <MailFolders :store="store" />
      <MailList :store="store" />
      <MailMessage :store="store" :compact="compact" />
    </div>
  </div>
</template>
