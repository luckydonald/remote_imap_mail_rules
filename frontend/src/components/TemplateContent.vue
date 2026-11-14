<script setup lang="ts">
import { provide } from 'vue'
import ConditionNode from './ConditionNode.vue'
import { CURRENT_TEMPLATE } from '@/model/context'
import type { Expression } from '@/model/types'

const props = defineProps<{ template: string }>()
const content = defineModel<Expression>({ required: true })

// Not reactive on purpose: the component is keyed by the template's name.
provide(CURRENT_TEMPLATE, props.template)
</script>

<template>
  <ConditionNode v-model="content" />
</template>
