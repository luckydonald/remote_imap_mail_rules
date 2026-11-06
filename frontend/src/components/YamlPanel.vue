<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchRules, saveRules, SaveError } from '@/model/api'
import { useStore } from '@/model/store/rules'
import { validateRules } from '@/model/validate'
import { parseRulesWithComments, RulesParseError } from '@/model/yaml-io'

const store = useStore()

/** What the text starts from: the server's own text while it is unchanged (its formatting and comments as they are), else the generated YAML. */
function base(): string {
  return store.serverFile !== null && !store.dirty && store.serverRaw !== ''
    ? store.serverRaw
    : store.yaml
}

const draft = ref(base())
const error = ref('')
const saved = ref('')
const saving = ref(false)
const dirty = computed(() => draft.value !== base())

watch([() => store.yaml, () => store.serverRaw], () => {
  draft.value = base()
  error.value = ''
})

/** What the draft would be: its problems, or why it cannot be read at all. */
const reading = computed(() => {
  if (!dirty.value) return { problems: store.problems, parseError: '' }
  try {
    return { problems: validateRules(parseRulesWithComments(draft.value).file), parseError: '' }
  } catch (caught) {
    return { problems: [], parseError: caught instanceof Error ? caught.message : String(caught) }
  }
})

const target = computed(() =>
  store.backend?.kind === 'database' ? 'the database' : (store.serverFile ?? ''),
)

function apply(): void {
  try {
    store.applyText(draft.value)
    error.value = ''
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : String(caught)
    if (!(caught instanceof RulesParseError)) console.error(caught)
  }
}

/** Writes the draft as typed, the server is the judge of it; then reads back what the server keeps. */
async function saveRaw(): Promise<void> {
  saving.value = true
  error.value = ''
  try {
    await saveRules(draft.value)
    const stored = (await fetchRules()) ?? draft.value
    store.applyText(stored)
    store.markSaved(undefined, store.yaml, stored)
    draft.value = base()
    saved.value = `Saved to ${target.value}.`
  } catch (caught) {
    error.value =
      caught instanceof SaveError
        ? `Not saved: ${caught.messages.join('; ')}`
        : `Not saved: ${caught instanceof Error ? caught.message : String(caught)}`
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="yaml-panel">
    <p v-if="store.serverFile !== null" class="hint">
      The text of {{ target }} on the server. Edit or paste it and save it as it is.
      <template v-if="store.backend?.kind === 'database'">
        The database keeps one row per rule, so comments end up in the rule descriptions and anchors
        are not kept.
      </template>
    </p>
    <p v-else class="hint">
      The generated file, in memory only and never written to the server. Paste a rules file here
      and apply it to replace the current one. Comments of the loaded text are kept as long as the
      commented entries still exist.
    </p>
    <ul v-if="reading.problems.length > 0" class="problems">
      <li v-for="(problem, i) in reading.problems" :key="i">
        <template v-if="!dirty">
          <button
            v-if="problem.rule !== null"
            type="button"
            class="link"
            @click="store.view = { kind: 'rule', index: problem.rule }"
          >
            rule {{ problem.rule + 1 }}
          </button>
          <button
            v-else-if="problem.template !== null"
            type="button"
            class="link"
            @click="store.view = { kind: 'templates' }"
          >
            template {{ problem.template }}
          </button>
        </template>
        <code>{{ problem.path }}</code> {{ problem.message }}
      </li>
    </ul>
    <p v-if="error || reading.parseError" class="message error">
      {{ error || reading.parseError }}
    </p>
    <p v-if="saved" class="message">{{ saved }}</p>
    <textarea
      v-model="draft"
      class="yaml"
      spellcheck="false"
      aria-label="YAML"
      @input="((error = ''), (saved = ''))"
    />
    <div class="row">
      <button type="button" :disabled="!dirty" @click="apply">Apply</button>
      <button
        v-if="store.serverFile !== null"
        type="button"
        class="save"
        :disabled="saving || (!dirty && !store.dirty)"
        :title="`Write the text above to ${target} as it is`"
        @click="saveRaw"
      >
        Save to {{ target }}
      </button>
      <button type="button" class="ghost" :disabled="!dirty" @click="draft = base()">Reset</button>
    </div>
  </section>
</template>
