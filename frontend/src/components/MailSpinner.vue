<script setup lang="ts">
/** A dancing mail emoji with a label (default "Loading…"), shown while mails are being fetched. */
withDefaults(defineProps<{ label?: string }>(), { label: 'Loading…' })
</script>

<template>
  <p class="mail-spinner" role="status">
    <span class="dancer" aria-hidden="true">📧</span>
    <span>{{ label }}</span>
  </p>
</template>
