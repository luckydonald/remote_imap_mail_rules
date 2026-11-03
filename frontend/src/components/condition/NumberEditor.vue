<script setup lang="ts">
import FieldValue from '../FieldValue.vue'
import { compareOperators, numberFields, operatorLabels, quantifiers } from '@/model/catalog'
import { isVar, type NumberCondition } from '@/model/types'

const model = defineModel<NumberCondition>('node', { required: true })

function setOperator(operator: string): void {
  const node = model.value
  node.operator = operator
  if (isVar(node.value)) return
  if (operator === 'between' && !Array.isArray(node.value)) node.value = [node.value, node.value]
  else if (operator !== 'between' && Array.isArray(node.value)) node.value = node.value[0]
}

function pair(): [number, number] {
  return Array.isArray(model.value.value) ? model.value.value : [0, 0]
}

function setPart(index: 0 | 1, event: Event): void {
  const next = [...pair()] as [number, number]
  next[index] = Number((event.target as HTMLInputElement).value)
  model.value.value = next
}
</script>

<template>
  <div class="leaf">
    <FieldValue v-model="model.field" fallback="size">
      <select v-model="model.field">
        <option v-for="field in numberFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.operator" fallback="gt">
      <select
        :value="model.operator"
        @change="setOperator(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="operator in compareOperators" :key="operator" :value="operator">
          {{ operatorLabels[operator] }}
        </option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.value" :fallback="0">
      <template v-if="model.operator === 'between'">
        <input type="number" :value="pair()[0]" @input="setPart(0, $event)" />
        <span>and</span>
        <input type="number" :value="pair()[1]" @input="setPart(1, $event)" />
      </template>
      <input v-else v-model.number="model.value as number" type="number" />
    </FieldValue>
    <FieldValue v-model="model.quantifier" fallback="any">
      <select v-model="model.quantifier">
        <option v-for="quantifier in quantifiers" :key="quantifier" :value="quantifier">
          {{ quantifier }}
        </option>
      </select>
    </FieldValue>
  </div>
</template>
