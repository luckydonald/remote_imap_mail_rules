<script setup lang="ts">
import { folderIcon, folderLabel } from '@/model/mail-format'
import type { MailStore } from '@/model/mail-store'
import MailSpinner from './MailSpinner.vue'

defineProps<{ store: MailStore }>()
</script>

<template>
  <nav class="mail-folders" aria-label="Folders">
    <label v-if="store.accounts.value.length > 1" class="account-pick">
      <span class="sr-only">Account</span>
      <select
        :value="store.accountId.value ?? ''"
        @change="store.selectAccount(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="account in store.accounts.value" :key="account.id" :value="account.id">
          {{ account.name }}
        </option>
      </select>
    </label>
    <MailSpinner v-if="store.foldersLoading.value" />
    <ul>
      <li v-for="item in store.folders.value" :key="item.name">
        <button
          type="button"
          class="folder"
          :class="{ active: item.name === store.folder.value }"
          :style="{ paddingLeft: `${12 + folderLabel(item).depth * 16}px` }"
          @click="store.selectFolder(item.name)"
        >
          <span class="icon" aria-hidden="true">{{ folderIcon(item) }}</span>
          <span class="name">{{ folderLabel(item).name }}</span>
          <span v-if="item.unseen" class="count">{{ item.unseen }}</span>
        </button>
      </li>
    </ul>
  </nav>
</template>
