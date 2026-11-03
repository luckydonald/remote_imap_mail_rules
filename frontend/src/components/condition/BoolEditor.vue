<script setup lang="ts">
import FieldValue from "../FieldValue.vue";
import { boolFields, quantifiers } from "@/model/catalog";
import type { BoolCondition } from "@/model/types";

defineProps<{ node: BoolCondition }>();
</script>

<template>
  <div class="leaf">
    <FieldValue v-model="node.field" fallback="seen">
      <select v-model="node.field">
        <option v-for="field in boolFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <span>is</span>
    <FieldValue v-model="node.value" :fallback="true">
      <select v-model="node.value">
        <option :value="true">true</option>
        <option :value="false">false</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.quantifier" fallback="any">
      <select v-model="node.quantifier">
        <option v-for="quantifier in quantifiers" :key="quantifier" :value="quantifier">{{ quantifier }}</option>
      </select>
    </FieldValue>
  </div>
</template>
