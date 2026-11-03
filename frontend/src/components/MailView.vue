<script setup lang="ts">
import { onMounted } from 'vue'
import MailFolders from './MailFolders.vue'
import MailList from './MailList.vue'
import MailMessage from './MailMessage.vue'
import { useMailStore } from '@/model/mail-store'

defineProps<{ compact?: boolean }>()
const emit = defineEmits<{ unauthorized: []; close: [] }>()

const store = useMailStore()

store.setUnauthorizedHandler(() => emit('unauthorized'))
onMounted(() => void store.loadAccounts())
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
