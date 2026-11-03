<script setup lang="ts">
import FieldValue from "../FieldValue.vue";
import { compareOperators, numberFields, operatorLabels, quantifiers } from "@/model/catalog";
import { isVar, type NumberCondition } from "@/model/types";

const props = defineProps<{ node: NumberCondition }>();

function setOperator(operator: string): void {
  const node = props.node;
  node.operator = operator;
  if (isVar(node.value)) return;
  if (operator === "between" && !Array.isArray(node.value)) node.value = [node.value, node.value];
  else if (operator !== "between" && Array.isArray(node.value)) node.value = node.value[0];
}

function pair(): [number, number] {
  return Array.isArray(props.node.value) ? props.node.value : [0, 0];
}

function setPart(index: 0 | 1, event: Event): void {
  const next = [...pair()] as [number, number];
  next[index] = Number((event.target as HTMLInputElement).value);
  props.node.value = next;
}
</script>

<template>
  <div class="leaf">
    <FieldValue v-model="node.field" fallback="size">
      <select v-model="node.field">
        <option v-for="field in numberFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.operator" fallback="gt">
      <select :value="node.operator" @change="setOperator(($event.target as HTMLSelectElement).value)">
        <option v-for="operator in compareOperators" :key="operator" :value="operator">{{ operatorLabels[operator] }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.value" :fallback="0">
      <template v-if="node.operator === 'between'">
        <input type="number" :value="pair()[0]" @input="setPart(0, $event)" />
        <span>and</span>
        <input type="number" :value="pair()[1]" @input="setPart(1, $event)" />
      </template>
      <input v-else v-model.number="node.value as number" type="number" />
    </FieldValue>
    <FieldValue v-model="node.quantifier" fallback="any">
      <select v-model="node.quantifier">
        <option v-for="quantifier in quantifiers" :key="quantifier" :value="quantifier">{{ quantifier }}</option>
      </select>
    </FieldValue>
  </div>
</template>
