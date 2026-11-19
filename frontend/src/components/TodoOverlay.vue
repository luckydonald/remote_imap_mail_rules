<script setup lang="ts">
import { defineAsyncComponent, onMounted, ref } from 'vue'
import { fetchTodoOverlayConfig } from '@/model/client-config'

const Overlay = defineAsyncComponent(async () => {
  const [overlay] = await Promise.all([
    import('@luckylu.cy/sync-todo-overlay/vue'),
    import('@luckylu.cy/sync-todo-overlay/style'),
  ])
  return overlay.default
})

const config = ref<Awaited<ReturnType<typeof fetchTodoOverlayConfig>>>(null)

onMounted(async () => {
  config.value = await fetchTodoOverlayConfig()
})
</script>

<template>
  <Overlay v-if="config" v-bind="config" />
</template>
