<script setup lang="ts">
/** `Rule ▾`: start a rule from the open mail, or add one of its values to a rule that exists, in any of its groups. */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { addressFields, boolFields, dateFields, numberFields, textFields } from '@/model/catalog'
import {
  appendCondition,
  conditionFor,
  granularities,
  groupsOf,
  type Granularity,
  type MailContext,
} from '@/model/fill-from-mail'
import { personLabel } from '@/model/mail-format'
import { useStore } from '@/model/store'
import { locationOfView } from '@/router'

const props = defineProps<{ context: MailContext }>()
const rules = useStore()
const router = useRouter()

const open = ref(false)
const dialog = ref(false)
const ruleIndex = ref(0)
const groupKey = ref('[]')
const field = ref('from')
const granularity = ref<Granularity>('address')

const fields = computed(() =>
  [...addressFields, ...textFields, ...numberFields, ...dateFields, ...boolFields].filter(
    (name) => conditionFor(name, props.context) !== null,
  ),
)
const chosen = computed(() => (fields.value.includes(field.value) ? field.value : fields.value[0]))
const isAddress = computed(() => chosen.value !== undefined && addressFields.includes(chosen.value))
const rule = computed(() => rules.file.rules[ruleIndex.value])
const groups = computed(() => (rule.value ? groupsOf(rule.value.when) : []))

// A group of another rule does not exist in this one, so the choice goes back to the root.
watch(ruleIndex, () => (groupKey.value = '[]'))

function groupLabel(group: { path: number[]; type: string; depth: number }): string {
  const place =
    group.path.length === 0 ? 'whole rule' : `child ${group.path.map((i) => i + 1).join('.')}`
  return `${'— '.repeat(group.depth)}${group.type} (${place})`
}

function newRule(): void {
  open.value = false
  const { detail, accountId, folder } = props.context
  const condition = conditionFor('from', props.context, 'address')
  rules.addRule()
  const created = rules.file.rules[rules.file.rules.length - 1]
  if (!created) return
  created.name = `From ${personLabel(detail.sender)}`
  created.locations = [{ account_id: accountId, folder, recursive: false }]
  if (condition) created.when = { type: 'all', conditions: [condition] }
  void router.push(locationOfView(rules.view))
}

function addTo(): void {
  const target = rule.value
  if (!target || !chosen.value) return
  const condition = conditionFor(chosen.value, props.context, granularity.value)
  if (!condition) return
  target.when = appendCondition(target.when, condition, JSON.parse(groupKey.value) as number[])
  rules.view = { kind: 'rule', index: ruleIndex.value }
  dialog.value = false
  void router.push(locationOfView(rules.view))
}
</script>

<template>
  <div class="menu" @keydown.esc="open = false">
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
      <button type="button" role="menuitem" @click="newRule">New rule from this mail</button>
      <button
        type="button"
        role="menuitem"
        :disabled="rules.file.rules.length === 0"
        @click="((dialog = true), (open = false))"
      >
        Add to existing rule …
      </button>
    </div>
    <!-- Out of the scrolling panes: Safari on an iPad clips a fixed dialog to the pane that holds it. -->
    <Teleport to="body">
      <div v-if="dialog" class="modal-backdrop" @click.self="dialog = false">
        <div class="modal" role="dialog" aria-modal="true" aria-label="Add to a rule">
          <h3>Add to a rule</h3>
          <label>
            Rule
            <select v-model.number="ruleIndex">
              <option v-for="(item, index) in rules.file.rules" :key="index" :value="index">
                {{ item.name }}
              </option>
            </select>
          </label>
          <label>
            Add to
            <select v-model="groupKey">
              <option
                v-for="group in groups"
                :key="JSON.stringify(group.path)"
                :value="JSON.stringify(group.path)"
              >
                {{ groupLabel(group) }}
              </option>
              <option v-if="groups.length === 0" value="[]">whole rule (wrapped in an all)</option>
            </select>
          </label>
          <label>
            Field
            <select v-model="field">
              <option v-for="item in fields" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label v-if="isAddress">
            Part of the address
            <select v-model="granularity">
              <option v-for="item in granularities" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
          <footer>
            <button type="button" class="ghost" @click="dialog = false">Cancel</button>
            <button type="button" class="add-condition" @click="addTo">Add condition</button>
          </footer>
        </div>
      </div>
    </Teleport>
  </div>
</template>
