<script setup lang="ts">
/** Shows the rules with a big clickable area at every place a condition can go; emits where it was clicked. */
import type { Rule } from '@/model/types'
import RuleInsertNode from './RuleInsertNode.vue'

defineProps<{ rules: Rule[] }>()
const emit = defineEmits<{ pick: [target: { ruleIndex: number; path: number[]; index: number }] }>()
</script>

<template>
  <ul class="insert-picker">
    <li v-for="(rule, ruleIndex) in rules" :key="ruleIndex" class="insert-rule">
      <h4>{{ rule.name }}<small v-if="rule.enabled === false"> (disabled)</small></h4>
      <RuleInsertNode
        :expr="rule.when"
        :path="[]"
        :rule-name="rule.name"
        @pick="(path, index) => emit('pick', { ruleIndex, path, index })"
      />
    </li>
  </ul>
</template>
