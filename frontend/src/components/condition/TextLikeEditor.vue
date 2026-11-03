<script setup lang="ts">
import FieldValue from '../FieldValue.vue'
import {
  addressFields,
  addressParts,
  operatorLabels,
  quantifiers,
  textFields,
  textOperators,
} from '@/model/catalog'
import {
  isVar,
  type AddressCondition,
  type HeaderCondition,
  type TextCondition,
} from '@/model/types'

const model = defineModel<TextCondition | HeaderCondition | AddressCondition>('node', {
  required: true,
})

function setOperator(operator: string): void {
  const node = model.value
  node.operator = operator
  if (isVar(node.value)) return
  if (operator === 'in' && typeof node.value === 'string')
    node.value = node.value === '' ? [] : [node.value]
  else if (operator !== 'in' && Array.isArray(node.value)) node.value = node.value.join(', ')
}

function listText(): string {
  return Array.isArray(model.value.value) ? model.value.value.join('\n') : ''
}

function setList(event: Event): void {
  model.value.value = (event.target as HTMLTextAreaElement).value
    .split('\n')
    .filter((line) => line !== '')
}
</script>

<template>
  <div class="leaf">
    <FieldValue v-if="model.type === 'header'" v-model="model.name" fallback="X-Header">
      <input v-model="model.name" placeholder="Header name" />
    </FieldValue>
    <FieldValue v-else v-model="model.field" :fallback="model.type === 'text' ? 'subject' : 'from'">
      <select v-model="model.field">
        <option
          v-for="field in model.type === 'text' ? textFields : addressFields"
          :key="field"
          :value="field"
        >
          {{ field }}
        </option>
      </select>
    </FieldValue>
    <FieldValue v-if="model.type === 'address'" v-model="model.part" fallback="address">
      <select v-model="model.part" title="Which part of the address to compare">
        <option v-for="part in addressParts" :key="part" :value="part">{{ part }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.operator" fallback="contains">
      <select
        :value="model.operator"
        @change="setOperator(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="operator in textOperators" :key="operator" :value="operator">
          {{ operatorLabels[operator] }}
        </option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.value" fallback="">
      <textarea
        v-if="model.operator === 'in'"
        rows="3"
        :value="listText()"
        placeholder="One value per line"
        @input="setList"
      />
      <input
        v-else
        v-model="model.value as string"
        :placeholder="model.operator === 'regex' ? 'regular expression' : 'value'"
      />
    </FieldValue>
    <FieldValue v-model="model.case_sensitive" :fallback="false">
      <label class="check"
        ><input v-model="model.case_sensitive" type="checkbox" /> case sensitive</label
      >
    </FieldValue>
    <FieldValue v-model="model.quantifier" fallback="any">
      <select
        v-model="model.quantifier"
        title="For multi-valued fields: how many values must match"
      >
        <option v-for="quantifier in quantifiers" :key="quantifier" :value="quantifier">
          {{ quantifier }}
        </option>
      </select>
    </FieldValue>
  </div>
</template>
