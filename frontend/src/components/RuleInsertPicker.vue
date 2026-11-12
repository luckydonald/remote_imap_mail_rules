<script setup lang="ts">
/** Shows the rules with a big clickable area at every place a condition can go; emits where it was clicked. */
import type { Rule } from '@/model/types'
import RuleInsertNode from './RuleInsertNode.vue'

/** `only`: show just the rule with this index (the emitted `ruleIndex` stays the real one). */
defineProps<{ rules: Rule[]; only?: number }>()
const emit = defineEmits<{ pick: [target: { ruleIndex: number; path: number[]; index: number }] }>()
</script>

<template>
  <ul class="insert-picker">
    <template v-for="(rule, ruleIndex) in rules" :key="ruleIndex">
      <li v-if="only === undefined || only === ruleIndex" class="insert-rule">
        <h4>{{ rule.name }}<small v-if="rule.enabled === false"> (disabled)</small></h4>
        <RuleInsertNode
          :expr="rule.when"
          :path="[]"
          :rule-name="rule.name"
          @pick="(path, index) => emit('pick', { ruleIndex, path, index })"
        />
      </li>
    </template>
  </ul>
</template>
