<script setup lang="ts">
import type { TimeValue } from "@/model/types";

const props = defineProps<{ modelValue: TimeValue }>();
const emit = defineEmits<{ "update:modelValue": [value: TimeValue] }>();

function setKind(event: Event): void {
  const relative = (event.target as HTMLSelectElement).value === "relative";
  emit("update:modelValue", relative ? { relative: true, value: "7d" } : { relative: false, value: new Date().toISOString() });
}

function setValue(event: Event): void {
  emit("update:modelValue", { ...props.modelValue, value: (event.target as HTMLInputElement).value } as TimeValue);
}

function localValue(): string {
  // `datetime-local` has no zone, the value is UTC (naive means UTC in the rules).
  return props.modelValue.value.replace(/(Z|[+-]\d\d:?\d\d)$/, "").slice(0, 19);
}

function setAbsolute(event: Event): void {
  const text = (event.target as HTMLInputElement).value;
  emit("update:modelValue", { relative: false, value: text === "" ? "" : `${text.length === 16 ? `${text}:00` : text}Z` });
}
</script>

<template>
  <span class="time-input">
    <select :value="modelValue.relative ? 'relative' : 'absolute'" @change="setKind">
      <option value="relative">ago</option>
      <option value="absolute">at (UTC)</option>
    </select>
    <input v-if="modelValue.relative" :value="modelValue.value" pattern="\d+[smhdw]" placeholder="7d" size="6" title="A number and a unit: s, m, h, d or w" @input="setValue" />
    <input v-else type="datetime-local" step="1" :value="localValue()" @input="setAbsolute" />
  </span>
</template>
