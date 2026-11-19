<script setup lang="ts">
import { computed } from 'vue'
import FieldValue from '../FieldValue.vue'
import { isVar, type Templatable, type TimeValue } from '@/model/types'

const model = defineModel<TimeValue>({ required: true })
const relative = computed(() => model.value.relative ?? false)
const fixedValue = computed(() => (isVar(model.value.value) ? '' : model.value.value))

function defaultValue(relative: Templatable<boolean>): string {
  if (isVar(relative)) return ''
  return relative ? '7d' : new Date().toISOString()
}

function setKind(relative: Templatable<boolean>): void {
  const { value } = model.value
  model.value = {
    relative,
    value: isVar(relative) || isVar(value) ? value : defaultValue(relative),
  }
}

function setValue(value: Templatable<string>): void {
  model.value = { ...model.value, value }
}

function localValue(): string {
  // `datetime-local` has no zone, the value is UTC (naive means UTC in the rules).
  return fixedValue.value.replace(/(Z|[+-]\d\d:?\d\d)$/, '').slice(0, 19)
}

function setAbsolute(event: Event): void {
  const text = (event.target as HTMLInputElement).value
  setValue(text === '' ? '' : `${text.length === 16 ? `${text}:00` : text}Z`)
}
</script>

<template>
  <span class="time-input">
    <FieldValue
      :model-value="relative"
      :fallback="true"
      var-name="relative"
      @update:model-value="setKind($event as Templatable<boolean>)"
    >
      <select
        aria-label="Date kind"
        :value="relative ? 'relative' : 'absolute'"
        @change="setKind(($event.target as HTMLSelectElement).value === 'relative')"
      >
        <option value="relative">ago</option>
        <option value="absolute">at (UTC)</option>
      </select>
    </FieldValue>
    <FieldValue
      :model-value="model.value"
      :fallback="defaultValue(relative)"
      var-name="value"
      @update:model-value="setValue($event as Templatable<string>)"
    >
      <input
        v-if="relative === false"
        aria-label="Date value"
        type="datetime-local"
        step="1"
        :value="localValue()"
        @input="setAbsolute"
      />
      <input
        v-else
        aria-label="Date value"
        :value="fixedValue"
        :pattern="relative === true ? '\\d+[smhdw]' : undefined"
        :placeholder="relative === true ? '7d' : undefined"
        :size="relative === true ? 6 : undefined"
        :title="relative === true ? 'A number and a unit: s, m, h, d or w' : undefined"
        @input="setValue(($event.target as HTMLInputElement).value)"
      />
    </FieldValue>
  </span>
</template>
