<script setup lang="ts">
import { computed, ref } from 'vue'
import { refillTemplateUse } from '@/model/fill-from-mail'
import { useStore } from '@/model/store'
import { parseValue as parse, showValue as show } from '@/model/values'
import { templateVariables } from '@/model/validate'
import type { TemplateUse } from '@/model/types'

const model = defineModel<TemplateUse>('node', { required: true })
const store = useStore()

const names = computed(() => Object.keys(store.file.templates))
const variables = computed(() => templateVariables(store.file, model.value.ref))
const defaults = computed(() => store.file.templates[model.value.ref]?.defaults ?? {})

/** Keys of this use that the template no longer has. */
const orphans = computed(() =>
  Object.keys(model.value.variables ?? {}).filter((key) => !variables.value.includes(key)),
)
/** Per orphan, the target the user picked while it waits for a decision about which value to keep. */
const asking = ref<Record<string, string>>({})

function suggestion(key: string): string {
  const to = store.pendingRenames[model.value.ref]?.find((entry) => entry.from === key)?.to
  return to !== undefined && variables.value.includes(to) ? to : ''
}

function moveTo(key: string, target: string): void {
  if (target === '') return
  if (store.resolveOrphan(model.value, key, target) === 'conflict') asking.value[key] = target
}

function keep(key: string, which: 'orphan' | 'target' | 'revert'): void {
  const target = asking.value[key]
  delete asking.value[key]
  if (which !== 'revert' && target !== undefined)
    store.resolveOrphan(model.value, key, target, which)
}

/** Points the use at another template; with an example mail open its variables are filled from it. */
function changeRef(ref: string): void {
  if (store.fillContext)
    model.value = refillTemplateUse(model.value, ref, store.file.templates, store.fillContext)
  else model.value.ref = ref
}

function set(name: string, event: Event): void {
  const text = (event.target as HTMLInputElement).value
  if (text === '') delete model.value.variables[name]
  else model.value.variables[name] = parse(text)
}
</script>

<template>
  <div class="template-use">
    <label>
      Template
      <select :value="model.ref" @change="changeRef(($event.target as HTMLSelectElement).value)">
        <option v-for="name in names" :key="name" :value="name">{{ name }}</option>
        <option v-if="!names.includes(model.ref)" :value="model.ref">
          {{ model.ref || '(none)' }} (missing)
        </option>
      </select>
    </label>
    <p v-if="names.length === 0" class="hint">
      There are no templates yet, create one under “Templates”.
    </p>
    <div v-for="name in variables" :key="name" class="variable">
      <label>
        <code>{{ name }}</code>
        <input
          :value="show(model.variables[name])"
          :placeholder="name in defaults ? `default: ${show(defaults[name])}` : 'required'"
          @input="set(name, $event)"
        />
      </label>
    </div>
    <div v-for="key in orphans" :key="key" class="orphan" role="alert">
      <code>{{ key }}</code> = <code>{{ show(model.variables[key]) }}</code>
      <span class="hint">is not a variable of the template.</span>
      <template v-if="key in asking">
        Keep
        <button type="button" @click="keep(key, 'orphan')">
          {{ show(model.variables[key]) }}
        </button>
        <button type="button" @click="keep(key, 'target')">
          {{ show(model.variables[asking[key] ?? '']) }}
        </button>
        <button type="button" @click="keep(key, 'revert')">Revert</button>
      </template>
      <template v-else>
        <select
          :value="suggestion(key)"
          :aria-label="`Rename ${key} to`"
          @change="moveTo(key, ($event.target as HTMLSelectElement).value)"
        >
          <option value="">rename to …</option>
          <option v-for="name in variables" :key="name" :value="name">{{ name }}</option>
        </select>
        <button
          type="button"
          class="ghost danger"
          title="Remove"
          @click="store.dropOrphan(model, key)"
        >
          🗑
        </button>
      </template>
    </div>
  </div>
</template>
