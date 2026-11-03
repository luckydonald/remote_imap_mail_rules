<script setup lang="ts">
import { computed } from 'vue'
import ActionsEditor from './ActionsEditor.vue'
import ConditionNode from './ConditionNode.vue'
import FieldValue from './FieldValue.vue'
import DryRunPanel from './DryRunPanel.vue'
import LocationsEditor from './LocationsEditor.vue'
import { useStore } from '@/model/context'
import { useMailStore } from '@/model/mail-store'
import type { Rule } from '@/model/types'

const model = defineModel<Rule>('rule', { required: true })
const props = defineProps<{ index: number }>()
const store = useStore()
const mail = useMailStore()

const problems = computed(() =>
  store.problems.value.filter((problem) => problem.rule === props.index),
)

function actions() {
  model.value.actions ??= []
  return model.value.actions
}

function setDescription(text: string): void {
  if (text === '') delete model.value.description
  else model.value.description = text
}
</script>

<template>
  <section class="rule-editor">
    <ul v-if="problems.length > 0" class="problems">
      <li v-for="(problem, i) in problems" :key="i">
        <code>{{ problem.path }}</code> {{ problem.message }}
      </li>
    </ul>
    <div class="row">
      <input v-model="model.name" class="title" placeholder="Rule name" aria-label="Rule name" />
      <FieldValue v-model="model.enabled" :fallback="true">
        <label class="check"><input v-model="model.enabled" type="checkbox" /> enabled</label>
      </FieldValue>
    </div>
    <textarea
      :value="model.description ?? ''"
      class="description wide"
      rows="2"
      placeholder="Description"
      aria-label="Rule description"
      @input="setDescription(($event.target as HTMLTextAreaElement).value)"
    />
    <h3>Where</h3>
    <LocationsEditor :locations="model.locations" />
    <h3>When</h3>
    <ConditionNode v-model="model.when" />
    <h3>Then</h3>
    <ActionsEditor :actions="actions()" />
    <DryRunPanel v-if="mail.active" :rule="model" />
  </section>
</template>
