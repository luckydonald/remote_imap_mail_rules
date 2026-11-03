<script setup lang="ts">
import FieldValue from "../FieldValue.vue";
import { addressFields, addressParts, operatorLabels, quantifiers, textFields, textOperators } from "@/model/catalog";
import { isVar, type AddressCondition, type HeaderCondition, type TextCondition } from "@/model/types";

const props = defineProps<{ node: TextCondition | HeaderCondition | AddressCondition }>();

function setOperator(operator: string): void {
  const node = props.node;
  node.operator = operator;
  if (isVar(node.value)) return;
  if (operator === "in" && typeof node.value === "string") node.value = node.value === "" ? [] : [node.value];
  else if (operator !== "in" && Array.isArray(node.value)) node.value = node.value.join(", ");
}

function listText(): string {
  return Array.isArray(props.node.value) ? props.node.value.join("\n") : "";
}

function setList(event: Event): void {
  props.node.value = (event.target as HTMLTextAreaElement).value.split("\n").filter((line) => line !== "");
}
</script>

<template>
  <div class="leaf">
    <FieldValue v-if="node.type === 'header'" v-model="node.name" fallback="X-Header">
      <input v-model="node.name" placeholder="Header name" />
    </FieldValue>
    <FieldValue v-else v-model="node.field" :fallback="node.type === 'text' ? 'subject' : 'from'">
      <select v-model="node.field">
        <option v-for="field in node.type === 'text' ? textFields : addressFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-if="node.type === 'address'" v-model="node.part" fallback="address">
      <select v-model="node.part" title="Which part of the address to compare">
        <option v-for="part in addressParts" :key="part" :value="part">{{ part }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.operator" fallback="contains">
      <select :value="node.operator" @change="setOperator(($event.target as HTMLSelectElement).value)">
        <option v-for="operator in textOperators" :key="operator" :value="operator">{{ operatorLabels[operator] }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.value" fallback="">
      <textarea v-if="node.operator === 'in'" rows="3" :value="listText()" placeholder="One value per line" @input="setList" />
      <input v-else v-model="node.value as string" :placeholder="node.operator === 'regex' ? 'regular expression' : 'value'" />
    </FieldValue>
    <FieldValue v-model="node.case_sensitive" :fallback="false">
      <label class="check"><input v-model="node.case_sensitive" type="checkbox" /> case sensitive</label>
    </FieldValue>
    <FieldValue v-model="node.quantifier" fallback="any">
      <select v-model="node.quantifier" title="For multi-valued fields: how many values must match">
        <option v-for="quantifier in quantifiers" :key="quantifier" :value="quantifier">{{ quantifier }}</option>
      </select>
    </FieldValue>
  </div>
</template>
