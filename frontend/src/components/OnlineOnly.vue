<script setup lang="ts">
import { useOnline } from '@/model/online'

const { isOnline } = useOnline()
</script>

<template>
  <!-- A disabled fieldset disables every button and field inside, for what needs the server. -->
  <fieldset
    class="online-only"
    :disabled="!isOnline"
    :title="isOnline ? undefined : 'Not available offline'"
  >
    <slot />
  </fieldset>
</template>

<style scoped>
.online-only {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
</style>
