<script setup lang="ts">
/** First step of the "Add to a rule" dialog: the rules to choose from, one button each. */
import { describeExpression } from '@/model/fill-from-mail'
import type { Rule } from '@/model/types'

defineProps<{ rules: Rule[] }>()
const emit = defineEmits<{ open: [ruleIndex: number] }>()
</script>

<template>
  <ul class="rule-index">
    <li v-for="(rule, ruleIndex) in rules" :key="ruleIndex">
      <button type="button" class="ghost" @click="emit('open', ruleIndex)">
        <span> {{ rule.name }}<small v-if="rule.enabled === false"> (disabled)</small> › </span>
        <small>{{ describeExpression(rule.when) }}</small>
      </button>
    </li>
  </ul>
</template>
