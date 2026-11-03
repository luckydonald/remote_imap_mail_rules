<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from '@/model/context'
import { parseValue as parse, showValue as show } from '@/model/values'
import { templateVariables } from '@/model/validate'
import type { TemplateUse } from '@/model/types'

const model = defineModel<TemplateUse>('node', { required: true })
const store = useStore()

const names = computed(() => Object.keys(store.file.templates))
const variables = computed(() => templateVariables(store.file, model.value.ref))
const defaults = computed(() => store.file.templates[model.value.ref]?.defaults ?? {})

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
      <select v-model="model.ref">
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
  </div>
</template>
