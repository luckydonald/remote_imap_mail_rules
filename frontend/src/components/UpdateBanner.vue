<script setup lang="ts">
import { ref } from 'vue'
import { applyUpdate, updateAvailable } from '@/model/update'
import { useStore } from '@/model/store'

const store = useStore()
const later = ref(false)
</script>

<template>
  <div v-if="updateAvailable && !later" class="update-banner" role="status">
    <span>A new version of the app is available.</span>
    <span v-if="store.dirty" class="hint">Unsaved rule edits will be lost on reload.</span>
    <button type="button" @click="applyUpdate()">Reload</button>
    <button type="button" class="ghost" @click="later = true">Later</button>
  </div>
</template>
