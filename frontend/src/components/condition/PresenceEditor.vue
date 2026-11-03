<script setup lang="ts">
import FieldValue from "../FieldValue.vue";
import { operatorLabels, presenceFields, presenceOperators } from "@/model/catalog";
import type { PresenceCondition } from "@/model/types";

const props = defineProps<{ node: PresenceCondition }>();

function setTarget(kind: string): void {
  if (kind === "header") {
    delete props.node.field;
    props.node.header = "X-Header";
  } else {
    delete props.node.header;
    props.node.field = "subject";
  }
}
</script>

<template>
  <div class="leaf">
    <select :value="node.header !== undefined ? 'header' : 'field'" @change="setTarget(($event.target as HTMLSelectElement).value)">
      <option value="field">field</option>
      <option value="header">header</option>
    </select>
    <FieldValue v-if="node.header !== undefined" v-model="node.header" fallback="X-Header">
      <input v-model="node.header" placeholder="Header name" />
    </FieldValue>
    <FieldValue v-else v-model="node.field" fallback="subject">
      <select v-model="node.field">
        <option v-for="field in presenceFields" :key="field" :value="field">{{ field }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.operator" fallback="exists">
      <select v-model="node.operator">
        <option v-for="operator in presenceOperators" :key="operator" :value="operator">{{ operatorLabels[operator] }}</option>
      </select>
    </FieldValue>
    <FieldValue v-model="node.value" :fallback="true">
      <select v-model="node.value">
        <option :value="true">true</option>
        <option :value="false">false</option>
      </select>
    </FieldValue>
    <p class="hint">A field that does not exist makes every other operator false, even “≠”. Use presence with <code>false</code> or <code>not</code> for absence.</p>
  </div>
</template>
