<script setup lang="ts">
import { computed, ref } from 'vue'
import { addressFields, boolFields, dateFields, numberFields, textFields } from '@/model/catalog'
import { useStore } from '@/model/store/rules'
import {
  appendCondition,
  conditionFor,
  granularities,
  type Granularity,
  type MailContext,
} from '@/model/fill-from-mail'

const props = defineProps<{ context: MailContext }>()
const store = useStore()

const fields = computed(() =>
  [...addressFields, ...textFields, ...numberFields, ...dateFields, ...boolFields].filter(
    (field) => conditionFor(field, props.context) !== null,
  ),
)
const field = ref('from')
const granularity = ref<Granularity>('address')

const chosen = computed(() => (fields.value.includes(field.value) ? field.value : fields.value[0]))
const isAddress = computed(() => chosen.value !== undefined && addressFields.includes(chosen.value))
const rule = computed(() => {
  const view = store.view
  return view.kind === 'rule' ? store.file.rules[view.index] : undefined
})

function add(): void {
  if (!rule.value || !chosen.value) return
  const condition = conditionFor(chosen.value, props.context, granularity.value)
  if (condition) rule.value.when = appendCondition(rule.value.when, condition)
}
</script>

<template>
  <section class="add-to-rule" aria-label="Add a condition from this mail">
    <select v-model="field" aria-label="Field">
      <option v-for="item in fields" :key="item" :value="item">{{ item }}</option>
    </select>
    <select v-if="isAddress" v-model="granularity" aria-label="Part of the address">
      <option v-for="item in granularities" :key="item.value" :value="item.value">
        {{ item.label }}
      </option>
    </select>
    <button type="button" class="add-condition" :disabled="!rule" @click="add">
      Add to the rule
    </button>
    <span v-if="!rule" class="hint">Select a rule in the editor first.</span>
  </section>
</template>
