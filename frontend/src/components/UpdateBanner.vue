<script setup lang="ts">
import { applyUpdate, dismissUpdate, updateAvailable, updateDismissed } from '@/model/update'
import { useStore } from '@/model/store'

const store = useStore()
</script>

<template>
  <div v-if="updateAvailable && !updateDismissed" class="update-banner" role="status">
    <span>A new version of the app is available.</span>
    <span v-if="store.dirty" class="hint">Unsaved rule edits will be lost on reload.</span>
    <button type="button" @click="applyUpdate()">Reload</button>
    <button type="button" class="ghost" @click="dismissUpdate()">Later</button>
  </div>
</template>
