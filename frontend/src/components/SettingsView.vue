<script setup lang="ts">
/** The settings screen, iOS style: an index of the parts, each one drills down to its own page with a back link. */
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AccountsView from './AccountsView.vue'
import ActionLogView from './ActionLogView.vue'
import GitView from './GitView.vue'
import OnlineOnly from './OnlineOnly.vue'
import SettingsGeneral from './SettingsGeneral.vue'
import SettingsStats from './SettingsStats.vue'

defineEmits<{ unauthorized: [] }>()

const route = useRoute()
const parts = [
  { name: 'settings-general', label: 'General' },
  { name: 'settings-accounts', label: 'Accounts' },
  { name: 'settings-git', label: 'Git' },
  { name: 'settings-log', label: 'Action log' },
  { name: 'settings-stats', label: 'Stats' },
] as const
const current = computed(() => route.name)
</script>

<template>
  <main v-if="current === 'settings'" class="settings-index">
    <h2>Settings</h2>
    <ul aria-label="Settings sections">
      <li v-for="part in parts" :key="part.name">
        <RouterLink :to="{ name: part.name }">{{ part.label }}</RouterLink>
      </li>
    </ul>
  </main>
  <template v-else>
    <RouterLink :to="{ name: 'settings' }" class="settings-back">‹ Settings</RouterLink>
    <OnlineOnly v-if="current === 'settings-accounts'"><AccountsView /></OnlineOnly>
    <OnlineOnly v-else-if="current === 'settings-git'"><GitView /></OnlineOnly>
    <OnlineOnly v-else-if="current === 'settings-log'">
      <ActionLogView @unauthorized="$emit('unauthorized')" />
    </OnlineOnly>
    <SettingsStats v-else-if="current === 'settings-stats'" />
    <SettingsGeneral v-else />
  </template>
</template>
