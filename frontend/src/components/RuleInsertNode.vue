<script setup lang="ts">
/** One expression of `RuleInsertPicker`: a group with a big insert area between its children, or a one-line condition. */
import { computed } from 'vue'
import { typeLabels } from '@/model/catalog'
import { describeExpression } from '@/model/fill-from-mail'
import type { Expression } from '@/model/types'

const props = defineProps<{
  expr: Expression
  path: number[]
  /** The rule's name, for the accessible names of the insert areas. */
  ruleName: string
}>()
const emit = defineEmits<{ pick: [path: number[], index: number] }>()

/** The expressions an insert area can sit between: the children of a group, the single child of a `not`, a lone root condition. */
const children = computed<Expression[]>(() => {
  const { expr } = props
  if (expr.type === 'all' || expr.type === 'any') return expr.conditions
  if (expr.type === 'not') return [expr.condition]
  return props.path.length === 0 ? [expr] : []
})
/** A lone root condition is its own row, not a group with a child. */
const isGroup = computed(() => ['all', 'any', 'not'].includes(props.expr.type))
/** The group's heading as in the editor: "All of (AND)", with the child count for all / any. */
const heading = computed(() => {
  const { expr } = props
  const name = typeLabels[expr.type]
  return expr.type === 'all' || expr.type === 'any' ? `${name} · ${expr.conditions.length}` : name
})
const label = computed(() =>
  props.path.length === 0 ? 'whole rule' : `child ${props.path.map((i) => i + 1).join('.')}`,
)
</script>

<template>
  <div v-if="isGroup || path.length === 0" class="insert-group" :class="`type-${expr.type}`">
    <div v-if="isGroup" class="insert-head">{{ heading }}</div>
    <template v-for="(child, index) in children" :key="index">
      <button
        type="button"
        class="insert-point"
        :aria-label="`Insert into ${ruleName}, ${label}, position ${index + 1}`"
        @click="emit('pick', path, index)"
      >
        + Insert here
      </button>
      <RuleInsertNode
        v-if="isGroup"
        :expr="child"
        :path="[...path, index]"
        :rule-name="ruleName"
        @pick="(p, i) => emit('pick', p, i)"
      />
      <div v-else class="insert-row" :class="`type-${child.type}`">
        {{ describeExpression(child) }}
      </div>
    </template>
    <button
      type="button"
      class="insert-point"
      :aria-label="`Insert into ${ruleName}, ${label}, position ${children.length + 1}`"
      @click="emit('pick', path, children.length)"
    >
      + Insert here
    </button>
  </div>
  <div v-else class="insert-row" :class="`type-${expr.type}`">
    {{ describeExpression(expr) }}
  </div>
</template>
