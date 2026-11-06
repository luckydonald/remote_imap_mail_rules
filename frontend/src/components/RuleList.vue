<script setup lang="ts">
import { useStore } from '@/model/store/rules'

const store = useStore()

function problemCount(index: number): number {
  return store.problems.filter((problem) => problem.rule === index).length
}

function isActive(index: number): boolean {
  return store.view.kind === 'rule' && store.view.index === index
}
</script>

<template>
  <nav class="rule-list" aria-label="Rules">
    <h2>Rules</h2>
    <ul>
      <li
        v-for="(rule, index) in store.file.rules"
        :key="index"
        :class="{ active: isActive(index), disabled: rule.enabled === false }"
      >
        <button type="button" class="select" @click="store.view = { kind: 'rule', index }">
          <span class="name">{{ rule.name || '(unnamed)' }}</span>
          <span
            v-if="problemCount(index) > 0"
            class="badge error"
            :title="`${problemCount(index)} problems`"
            >{{ problemCount(index) }}</span
          >
          <span v-if="rule.enabled === false" class="badge">off</span>
        </button>
        <span v-if="isActive(index)" class="tools">
          <button
            type="button"
            class="ghost"
            title="Move up"
            :disabled="index === 0"
            @click="store.moveRule(index, -1)"
          >
            ↑
          </button>
          <button
            type="button"
            class="ghost"
            title="Move down"
            :disabled="index === store.file.rules.length - 1"
            @click="store.moveRule(index, 1)"
          >
            ↓
          </button>
          <button type="button" class="ghost" title="Duplicate" @click="store.duplicateRule(index)">
            ⧉
          </button>
          <button
            type="button"
            class="ghost danger"
            title="Delete"
            @click="store.removeRule(index)"
          >
            ✕
          </button>
        </span>
      </li>
    </ul>
    <button type="button" class="add" @click="store.addRule()">+ New rule</button>
    <h2>File</h2>
    <ul>
      <li :class="{ active: store.view.kind === 'templates' }">
        <button type="button" class="select" @click="store.view = { kind: 'templates' }">
          <span class="name">Templates</span>
          <span class="badge">{{ Object.keys(store.file.templates).length }}</span>
        </button>
      </li>
      <li :class="{ active: store.view.kind === 'yaml' }">
        <button type="button" class="select" @click="store.view = { kind: 'yaml' }">
          <span class="name">YAML</span>
          <span v-if="store.problems.length > 0" class="badge error">{{
            store.problems.length
          }}</span>
        </button>
      </li>
    </ul>
  </nav>
</template>
