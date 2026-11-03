<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useStore } from '@/model/context'
import { RulesParseError } from '@/model/yaml-io'

const store = useStore()
const draft = ref(store.yaml.value)
const error = ref('')
const dirty = computed(() => draft.value !== store.yaml.value)

watch(store.yaml, (yaml) => {
  draft.value = yaml
  error.value = ''
})

function apply(): void {
  try {
    store.load(draft.value)
    error.value = ''
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : String(caught)
    if (!(caught instanceof RulesParseError)) console.error(caught)
  }
}
</script>

<template>
  <section class="yaml-panel">
    <p class="hint">
      The generated file. Paste a rules file here and apply it to replace the current one. Comments
      are not kept.
    </p>
    <ul v-if="store.problems.value.length > 0" class="problems">
      <li v-for="(problem, i) in store.problems.value" :key="i">
        <button
          v-if="problem.rule !== null"
          type="button"
          class="link"
          @click="store.view.value = { kind: 'rule', index: problem.rule }"
        >
          rule {{ problem.rule + 1 }}
        </button>
        <button
          v-else-if="problem.template !== null"
          type="button"
          class="link"
          @click="store.view.value = { kind: 'templates' }"
        >
          template {{ problem.template }}
        </button>
        <code>{{ problem.path }}</code> {{ problem.message }}
      </li>
    </ul>
    <p v-if="error" class="message error">{{ error }}</p>
    <textarea v-model="draft" class="yaml" spellcheck="false" aria-label="YAML" />
    <div class="row">
      <button type="button" :disabled="!dirty" @click="apply">Apply</button>
      <button type="button" class="ghost" :disabled="!dirty" @click="draft = store.yaml.value">
        Reset
      </button>
    </div>
  </section>
</template>
