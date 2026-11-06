<script setup lang="ts">
import { computed, ref } from 'vue'
import ConfirmUnwrap from './ConfirmUnwrap.vue'
import AddressEditor from './condition/TextLikeEditor.vue'
import BoolEditor from './condition/BoolEditor.vue'
import DateEditor from './condition/DateEditor.vue'
import GroupEditor from './condition/GroupEditor.vue'
import NumberEditor from './condition/NumberEditor.vue'
import PresenceEditor from './condition/PresenceEditor.vue'
import TemplateUseEditor from './condition/TemplateUseEditor.vue'
import { expressionTypes, newExpression, typeLabels, type ExpressionType } from '@/model/catalog'
import { useStore } from '@/model/store'
import { fillExpression, type Granularity } from '@/model/fill-from-mail'
import { useClipboardStore } from '@/model/clipboard'
import type { Expression } from '@/model/types'

const props = defineProps<{ modelValue: Expression; removable?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: Expression]
  remove: []
  unwrap: []
}>()
const store = useStore()
const clipboard = useClipboardStore()

const node = computed(() => props.modelValue)
const isGroup = computed(() => ['all', 'any', 'not'].includes(node.value.type))

function changeType(type: ExpressionType): void {
  const current = node.value
  if ((type === 'all' || type === 'any') && (current.type === 'all' || current.type === 'any')) {
    emit('update:modelValue', { ...current, type })
    return
  }
  const created = newExpression(type, Object.keys(store.file.templates))
  // With a mail open the new condition starts from it.
  emit(
    'update:modelValue',
    store.fillContext
      ? fillExpression(created, store.fillContext, 'address', store.file.templates)
      : created,
  )
}

const fillable = computed(() =>
  ['text', 'address', 'header', 'number', 'date', 'bool'].includes(node.value.type),
)

/** Takes the value from the open mail, or opens the mail panel to choose one. */
function fillFromMail(): void {
  const context = store.fillContext
  if (!context) {
    store.panelOpen = true
    return
  }
  const current = node.value
  const part =
    current.type === 'address' && typeof current.part === 'string'
      ? (current.part as Granularity)
      : 'address'
  emit('update:modelValue', fillExpression(current, context, part))
}

/** Keeps the block (and its sub-blocks) for pasting and takes it out; the root and a `not` child are replaced by a fresh condition. */
function cut(): void {
  void clipboard.cut(node.value)
  if (props.removable) emit('remove')
  else emit('update:modelValue', newExpression('text'))
}

/** The expressions directly inside a group. */
const children = computed<Expression[]>(() => {
  const current = node.value
  if (current.type === 'not') return [current.condition]
  if (current.type === 'all' || current.type === 'any') return current.conditions
  return []
})
const asking = ref(false)
/** A group in a list hands its children to the parent, a single slot takes exactly one. */
const canUnwrap = computed(() => isGroup.value && (props.removable || children.value.length === 1))

function unwrap(): void {
  asking.value = false
  if (!canUnwrap.value) return
  if (props.removable) emit('unwrap')
  else emit('update:modelValue', children.value[0]!)
}

/** A group with children asks whether to keep them. */
function askRemove(): void {
  if (isGroup.value && children.value.length > 0) asking.value = true
  else emit('remove')
}

function confirmRemove(): void {
  asking.value = false
  emit('remove')
}

function wrap(type: 'all' | 'any' | 'not'): void {
  emit(
    'update:modelValue',
    type === 'not' ? { type, condition: node.value } : { type, conditions: [node.value] },
  )
}
</script>

<template>
  <div class="node" :class="[`node-${node.type}`, { group: isGroup }]">
    <div class="node-bar">
      <select
        :value="node.type"
        aria-label="Condition type"
        @change="changeType(($event.target as HTMLSelectElement).value as ExpressionType)"
      >
        <option v-for="type in expressionTypes" :key="type" :value="type">
          {{ typeLabels[type] }}
        </option>
      </select>
      <span class="spacer" />
      <button
        v-if="fillable && store.active"
        type="button"
        class="ghost fill-from-mail"
        :title="
          store.fillContext ? 'Fill the value from the open mail' : 'Choose a mail to fill from'
        "
        @click="fillFromMail"
      >
        From mail
      </button>
      <button
        type="button"
        class="ghost cut"
        title="Cut this block, to paste it into a group"
        @click="cut"
      >
        ✂ Cut
      </button>
      <button type="button" class="ghost" title="Wrap in NOT" @click="wrap('not')">not(…)</button>
      <button type="button" class="ghost" title="Wrap in ALL (AND)" @click="wrap('all')">
        all(…)
      </button>
      <button type="button" class="ghost" title="Wrap in ANY (OR)" @click="wrap('any')">
        any(…)
      </button>
      <button
        v-if="isGroup"
        type="button"
        class="ghost unwrap"
        :disabled="!canUnwrap"
        :title="
          canUnwrap
            ? 'Replace this group by its children'
            : 'Only a group with a single condition can be unwrapped here'
        "
        @click="unwrap"
      >
        ⤴ Unwrap
      </button>
      <button v-if="removable" type="button" class="ghost danger" title="Remove" @click="askRemove">
        ✕
      </button>
    </div>
    <ConfirmUnwrap
      v-if="asking"
      :count="children.length"
      @keep="unwrap"
      @remove="confirmRemove"
      @cancel="asking = false"
    />
    <GroupEditor
      v-if="node.type === 'all' || node.type === 'any' || node.type === 'not'"
      :node="node"
    />
    <AddressEditor
      v-else-if="node.type === 'text' || node.type === 'address' || node.type === 'header'"
      :node="node"
      @update:node="emit('update:modelValue', $event)"
    />
    <NumberEditor v-else-if="node.type === 'number'" :node="node" />
    <DateEditor v-else-if="node.type === 'date'" :node="node" />
    <BoolEditor v-else-if="node.type === 'bool'" :node="node" />
    <PresenceEditor v-else-if="node.type === 'presence'" :node="node" />
    <TemplateUseEditor v-else-if="node.type === 'template'" :node="node" />
  </div>
</template>
