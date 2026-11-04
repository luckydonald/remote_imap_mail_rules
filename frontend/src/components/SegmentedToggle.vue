<script setup lang="ts" generic="T extends string">
/** A row of buttons of which exactly one is on, e.g. `[ Text | HTML ]`. */
defineProps<{
  modelValue: T
  options: { value: T; label: string; disabled?: boolean }[]
  label: string
}>()
defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="segmented" role="radiogroup" :aria-label="label">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="option.value === modelValue"
      :class="{ on: option.value === modelValue }"
      :disabled="option.disabled"
      @click="$emit('update:modelValue', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>
