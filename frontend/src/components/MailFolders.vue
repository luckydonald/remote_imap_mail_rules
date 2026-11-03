<script setup lang="ts">
import { folderIcon, folderLabel } from '@/model/mail-format'
import type { MailStore } from '@/model/mail-store'
import MailSpinner from './MailSpinner.vue'

defineProps<{ store: MailStore }>()
</script>

<template>
  <nav class="mail-folders" aria-label="Folders">
    <label v-if="store.accounts.length > 1" class="account-pick">
      <span class="sr-only">Account</span>
      <select
        :value="store.accountId ?? ''"
        @change="store.selectAccount(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="account in store.accounts" :key="account.id" :value="account.id">
          {{ account.name }}
        </option>
      </select>
    </label>
    <MailSpinner v-if="store.foldersLoading" />
    <ul>
      <li v-for="item in store.folders" :key="item.name">
        <button
          type="button"
          class="folder"
          :class="{ active: item.name === store.folder }"
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
