<script setup lang="ts">
import ConditionNode from '../ConditionNode.vue'
import { newExpression } from '@/model/catalog'
import { fillExpression } from '@/model/fill-from-mail'
import { useMailStore } from '@/model/mail-store'
import type { GroupAll, GroupAny, GroupNot } from '@/model/types'

const mail = useMailStore()
const model = defineModel<GroupAll | GroupAny | GroupNot>('node', { required: true })

function add(): void {
  if (model.value.type === 'not') return
  const added = newExpression('text')
  // With a mail open the new condition starts from it.
  model.value.conditions.push(mail.fillContext ? fillExpression(added, mail.fillContext) : added)
}

function remove(index: number): void {
  if (model.value.type !== 'not') model.value.conditions.splice(index, 1)
}
</script>

<template>
  <div class="children">
    <template v-if="model.type === 'not'">
      <ConditionNode v-model="model.condition" />
    </template>
    <template v-else>
      <p v-if="model.conditions.length === 0" class="hint">A group needs at least one condition.</p>
      <ConditionNode
        v-for="(_, index) in model.conditions"
        :key="index"
        :model-value="model.conditions[index]!"
        @update:model-value="model.conditions[index] = $event"
        removable
        @remove="remove(index)"
      />
      <button type="button" class="add" @click="add">+ Add condition</button>
    </template>
  </div>
</template>
