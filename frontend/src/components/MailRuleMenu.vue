<script setup lang="ts">
/** `Rule ▾`: start a rule from the open mail, or add one of its values to a rule that exists, at any place of it. */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { addressFields, boolFields, dateFields, numberFields, textFields } from '@/model/catalog'
import {
  appendCondition,
  conditionFor,
  granularities,
  templateUseFor,
  type Granularity,
  type MailContext,
} from '@/model/fill-from-mail'
import { personLabel } from '@/model/mail-format'
import { useStore } from '@/model/store'
import { useMenu } from '@/model/menu'
import { locationOfView } from '@/router'
import RuleInsertPicker from './RuleInsertPicker.vue'

const props = defineProps<{ context: MailContext }>()
const store = useStore()
const router = useRouter()

const root = ref<HTMLElement | null>(null)
const open = useMenu('rule', root)
const dialog = ref(false)
const field = ref('from')
const granularity = ref<Granularity>('address')
const kind = ref<'condition' | 'template'>('condition')
const templateRef = ref('')

const templateNames = computed(() => Object.keys(store.file.templates))
const chosenTemplate = computed(() =>
  templateNames.value.includes(templateRef.value) ? templateRef.value : templateNames.value[0],
)
const templateUse = computed(() => {
  const ref = chosenTemplate.value
  const def = ref === undefined ? undefined : store.file.templates[ref]
  return ref === undefined || !def ? null : templateUseFor(ref, def, props.context)
})
const filledVariables = computed(() => Object.entries(templateUse.value?.variables ?? {}))

const fields = computed(() =>
  [...addressFields, ...textFields, ...numberFields, ...dateFields, ...boolFields].filter(
    (name) => conditionFor(name, props.context) !== null,
  ),
)
const chosen = computed(() => (fields.value.includes(field.value) ? field.value : fields.value[0]))
const isAddress = computed(() => chosen.value !== undefined && addressFields.includes(chosen.value))

/** Makes the open mail the editor's example, without touching a rule. */
function selectExample(): void {
  open.value = false
  store.fillDetached = false
  void router.push(locationOfView(store.view))
}

function newRule(): void {
  open.value = false
  const { detail, accountId, folder } = props.context
  const condition = conditionFor('from', props.context, 'address')
  store.addRule()
  const created = store.file.rules[store.file.rules.length - 1]
  if (!created) return
  created.name = `From ${personLabel(detail.sender)}`
  created.locations = [{ account_id: accountId, folder, recursive: false }]
  if (condition) created.when = { type: 'all', conditions: [condition] }
  void router.push(locationOfView(store.view))
}

function addTo(place: { ruleIndex: number; path: number[]; index: number }): void {
  const target = store.file.rules[place.ruleIndex]
  if (!target) return
  const condition =
    kind.value === 'template'
      ? templateUse.value
      : chosen.value
        ? conditionFor(chosen.value, props.context, granularity.value)
        : null
  if (!condition) return
  target.when = appendCondition(target.when, condition, place.path, place.index)
  store.view = { kind: 'rule', index: place.ruleIndex }
  dialog.value = false
  void router.push(locationOfView(store.view))
}
</script>

<template>
  <div ref="root" class="menu">
    <button
      type="button"
      class="ghost"
      aria-haspopup="menu"
      :aria-expanded="open"
      @click="open = !open"
    >
      Rule ▾
    </button>
    <div v-if="open" class="menu-pop end" role="menu">
      <button type="button" role="menuitem" @click="selectExample">Select as example mail</button>
      <button type="button" role="menuitem" @click="newRule">New rule from this mail</button>
      <button
        type="button"
        role="menuitem"
        :disabled="store.file.rules.length === 0"
        @click="((dialog = true), (open = false))"
      >
        Add to existing rule …
      </button>
    </div>
    <!-- Out of the scrolling panes: Safari on an iPad clips a fixed dialog to the pane that holds it. -->
    <Teleport to="body">
      <div v-if="dialog" class="modal-backdrop" @click.self="dialog = false">
        <div
          class="modal modal-wide add-to-rule-dialog"
          role="dialog"
          aria-modal="true"
          aria-label="Add to a rule"
        >
          <header class="modal-head">
            <button type="button" class="ghost back" @click="dialog = false">‹ Back</button>
            <h3>Add to a rule</h3>
          </header>
          <label>
            Add
            <select v-model="kind" aria-label="Kind of condition">
              <option value="condition">Condition</option>
              <option value="template" :disabled="templateNames.length === 0">Template</option>
            </select>
          </label>
          <label v-if="kind === 'template'">
            Template
            <select v-model="templateRef" aria-label="Template">
              <option v-for="name in templateNames" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
          <p v-if="kind === 'template'" class="template-fill">
            <template v-if="filledVariables.length">
              Filled from the mail:
              <code v-for="[name, value] in filledVariables" :key="name"
                >{{ name }} = {{ value }}</code
              >
            </template>
            <template v-else>Nothing to fill from this mail, the defaults apply.</template>
          </p>
          <label v-if="kind === 'condition'">
            Field
            <select v-model="field">
              <option v-for="item in fields" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label v-if="kind === 'condition' && isAddress">
            Part of the address
            <select v-model="granularity">
              <option v-for="item in granularities" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
          <h4 class="pick-title">Click where it should go</h4>
          <RuleInsertPicker :rules="store.file.rules" @pick="addTo" />
          <footer>
            <button type="button" class="ghost" @click="dialog = false">Cancel</button>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>
