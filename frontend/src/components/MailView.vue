<script setup lang="ts">
import { onMounted } from 'vue'
import MailFolders from './MailFolders.vue'
import MailList from './MailList.vue'
import MailMessage from './MailMessage.vue'
import { createMailStore } from '@/model/mail-store'

const emit = defineEmits<{ unauthorized: [] }>()

const store = createMailStore(() => emit('unauthorized'))

onMounted(() => void store.loadAccounts())
</script>

<template>
  <div class="mail" :data-pane="store.pane.value">
    <p
      v-if="store.error.value && !store.detail.value && store.selectedUid.value === null"
      class="message error"
    >
      {{ store.error.value }}
    </p>
    <p v-if="store.accounts.value.length === 0 && !store.error.value" class="hint empty">
      No accounts yet, add one on the Accounts screen.
    </p>
    <MailFolders :store="store" />
    <MailList :store="store" />
    <MailMessage :store="store" />
  </div>
</template>
