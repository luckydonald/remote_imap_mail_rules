<script setup lang="ts">
import FieldValue from '../FieldValue.vue'
import TimeInput from './TimeInput.vue'
import { compareOperators, dateFields, operatorLabels } from '@/model/catalog'
import { isVar, type DateCondition, type TimeValue } from '@/model/types'

const model = defineModel<DateCondition>('node', { required: true })

const fresh = (): TimeValue => ({ relative: true, value: '7d' })

function setOperator(operator: string): void {
  const node = model.value
  node.operator = operator
  if (isVar(node.value)) return
  if (operator === 'between' && !Array.isArray(node.value)) node.value = [node.value, node.value]
  else if (operator !== 'between' && Array.isArray(node.value))
    node.value = node.value[0] ?? fresh()
}

function part(index: 0 | 1): TimeValue {
  return Array.isArray(model.value.value) ? (model.value.value[index] ?? fresh()) : fresh()
}

function setPart(index: 0 | 1, value: TimeValue): void {
  const next: [TimeValue, TimeValue] = [part(0), part(1)]
  next[index] = value
  model.value.value = next
}
</script>

<template>
  <div class="leaf">
    <FieldValue v-model="model.field" fallback="date_received">
      <select v-model="model.field">
        <option v-for="field in dateFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.operator" fallback="lt">
      <select
        :value="model.operator"
        @change="setOperator(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="operator in compareOperators" :key="operator" :value="operator">
          {{ operatorLabels[operator] }}
        </option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.value" :fallback="fresh()">
      <template v-if="model.operator === 'between'">
        <TimeInput :model-value="part(0)" @update:model-value="setPart(0, $event)" />
        <span>and</span>
        <TimeInput :model-value="part(1)" @update:model-value="setPart(1, $event)" />
      </template>
      <TimeInput v-else-if="!Array.isArray(model.value)" v-model="model.value as TimeValue" />
    </FieldValue>
    <p class="hint" v-if="model.field === 'date_received' || model.field === 'date_sent'">
      “<code>lt 7d</code>” means older than a week, “<code>gt 7d</code>” means newer.
    </p>
  </div>
</template>
