<script setup lang="ts">
import FieldValue from '../FieldValue.vue'
import { boolFields, quantifiers } from '@/model/catalog'
import type { BoolCondition } from '@/model/types'

const model = defineModel<BoolCondition>('node', { required: true })
</script>

<template>
  <div class="leaf">
    <FieldValue v-model="model.field" fallback="seen">
      <select v-model="model.field">
        <option v-for="field in boolFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <span>is</span>
    <FieldValue v-model="model.value" :fallback="true">
      <select v-model="model.value">
        <option :value="true">true</option>
        <option :value="false">false</option>
      </select>
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
