<script setup lang="ts">
import ConditionNode from "../ConditionNode.vue";
import { newExpression } from "@/model/catalog";
import type { GroupAll, GroupAny, GroupNot } from "@/model/types";

const props = defineProps<{ node: GroupAll | GroupAny | GroupNot }>();

function add(): void {
  if (props.node.type !== "not") props.node.conditions.push(newExpression("text"));
}

function remove(index: number): void {
  if (props.node.type !== "not") props.node.conditions.splice(index, 1);
}
</script>

<template>
  <div class="children">
    <template v-if="node.type === 'not'">
      <ConditionNode v-model="node.condition" />
    </template>
    <template v-else>
      <p v-if="node.conditions.length === 0" class="hint">A group needs at least one condition.</p>
      <ConditionNode
        v-for="(_, index) in node.conditions"
        :key="index"
        :model-value="node.conditions[index]!"
        @update:model-value="node.conditions[index] = $event"
        removable
        @remove="remove(index)"
      />
      <button type="button" class="add" @click="add">+ Add condition</button>
    </template>
  </div>
</template>
