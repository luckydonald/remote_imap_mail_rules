<script setup lang="ts">
import { provide, ref } from 'vue'
import ConditionNode from './ConditionNode.vue'
import TemplateRenameBox from './TemplateRenameBox.vue'
import { newExpression } from '@/model/catalog'
import { ALLOW_VARS } from '@/model/context'
import { useStore } from '@/model/store'
import { parseValue, showValue } from '@/model/values'
import { templateVariables } from '@/model/validate'

provide(ALLOW_VARS, true)
const store = useStore()
const newName = ref('')
const message = ref('')

function create(): void {
  const name = newName.value.trim()
  if (name === '' || name in store.file.templates) {
    message.value =
      name === '' ? 'Give the template a name.' : `A template called \`${name}\` exists already.`
    return
  }
  store.file.templates[name] = { type: 'template', defaults: {}, content: newExpression('text') }
  newName.value = ''
  message.value = ''
}

function remove(name: string): void {
  const uses = store.usesOf(name)
  if (uses.rules.length + uses.templates.length > 0) {
    message.value = `\`${name}\` is used by ${[...uses.rules.map((i) => `rule ${i + 1}`), ...uses.templates.map((t) => `template ${t}`)].join(', ')}.`
    return
  }
  delete store.file.templates[name]
  message.value = ''
}

function rename(name: string, event: Event): void {
  const input = event.target as HTMLInputElement
  if (!store.renameTemplate(name, input.value.trim())) input.value = name
}

function setDefault(defaults: Record<string, unknown>, name: string, event: Event): void {
  const text = (event.target as HTMLInputElement).value
  if (text === '') delete defaults[name]
  else defaults[name] = parseValue(text)
}
</script>

<template>
  <section class="templates">
    <p class="hint">
      A template is an expression with variables. Switch a field to “var” to make it a variable, and
      use the template from any condition via the type “Template”.
    </p>
    <p v-if="message" class="message">{{ message }}</p>
    <article v-for="(def, name) in store.file.templates" :key="name" class="template">
      <header class="row">
        <input
          class="title"
          :value="name"
          aria-label="Template name"
          @change="rename(String(name), $event)"
        />
        <button
          type="button"
          class="ghost danger"
          title="Delete template"
          @click="remove(String(name))"
        >
          ✕
        </button>
      </header>
      <TemplateRenameBox :template="String(name)" />
      <h3>Variables</h3>
      <p v-if="templateVariables(store.file, String(name)).length === 0" class="hint">
        No variables yet.
      </p>
      <div
        v-for="variable in templateVariables(store.file, String(name))"
        :key="variable"
        class="row"
      >
        <code>{{ variable }}</code>
        <input
          :value="showValue(def.defaults[variable])"
          placeholder="default (empty = required)"
          @input="setDefault(def.defaults, variable, $event)"
        />
      </div>
      <template
        v-for="extra in Object.keys(def.defaults).filter(
          (key) => !templateVariables(store.file, String(name)).includes(key),
        )"
        :key="extra"
      >
        <div class="row">
          <code>{{ extra }}</code>
          <input
            :value="showValue(def.defaults[extra])"
            @input="setDefault(def.defaults, extra, $event)"
          />
          <span class="badge error">unused default</span>
        </div>
      </template>
      <h3>Content</h3>
      <ConditionNode v-model="def.content" />
    </article>
    <form class="row" @submit.prevent="create">
      <input v-model="newName" placeholder="New template name" />
      <button type="submit" class="add">+ Add template</button>
    </form>
  </section>
</template>
