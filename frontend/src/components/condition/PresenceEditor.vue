<script setup lang="ts">
import FieldValue from '../FieldValue.vue'
import { operatorLabels, presenceFields, presenceOperators } from '@/model/catalog'
import type { PresenceCondition } from '@/model/types'

const model = defineModel<PresenceCondition>('node', { required: true })

function setTarget(kind: string): void {
  if (kind === 'header') {
    delete model.value.field
    model.value.header = 'X-Header'
  } else {
    delete model.value.header
    model.value.field = 'subject'
  }
}
</script>

<template>
  <div class="leaf">
    <select
      :value="model.header !== undefined ? 'header' : 'field'"
      @change="setTarget(($event.target as HTMLSelectElement).value)"
    >
      <option value="field">field</option>
      <option value="header">header</option>
    </select>
    <FieldValue v-if="model.header !== undefined" v-model="model.header" fallback="X-Header">
      <input v-model="model.header" placeholder="Header name" />
    </FieldValue>
    <FieldValue v-else v-model="model.field" fallback="subject">
      <select v-model="model.field">
        <option v-for="field in presenceFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.operator" fallback="exists">
      <select v-model="model.operator">
        <option v-for="operator in presenceOperators" :key="operator" :value="operator">
          {{ operatorLabels[operator] }}
        </option>
      </select>
    </FieldValue>
    <FieldValue v-model="model.value" :fallback="true">
      <select v-model="model.value">
        <option :value="true">true</option>
        <option :value="false">false</option>
      </select>
    </FieldValue>
    <p class="hint">
      A field that does not exist makes every other operator false, even “≠”. Use presence with
      <code>false</code> or <code>not</code> for absence.
    </p>
  </div>
</template>
