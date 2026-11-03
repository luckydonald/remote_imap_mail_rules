<script setup lang="ts">
import FieldValue from './FieldValue.vue'
import { actionTypes } from '@/model/catalog'
import type { Action } from '@/model/types'

const model = defineModel<Action[]>('actions', { required: true })

function make(type: string): Action {
  switch (type) {
    case 'move':
      return { type: 'move', folder: 'Archive' }
    case 'flag':
      return { type: 'flag', value: true }
    case 'keyword':
      return { type: 'keyword', keyword: '', value: true }
    case 'mark_unread':
      return { type: 'mark_unread' }
    default:
      return { type: 'mark_read' }
  }
}
</script>

<template>
  <div class="model">
    <p class="hint">Actions are saved and checked, but nothing executes them yet.</p>
    <div v-for="(action, index) in model" :key="index" class="row">
      <select
        :value="action.type"
        @change="model[index] = make(($event.target as HTMLSelectElement).value)"
      >
        <option v-for="type in actionTypes" :key="type" :value="type">{{ type }}</option>
      </select>
      <template v-if="action.type === 'move'">
        <FieldValue v-model="action.folder" fallback="Archive">
          <input v-model="action.folder as string" placeholder="Target folder" />
        </FieldValue>
        <input
          v-model="action.account_id as string"
          class="wide mono"
          placeholder="Target account id (optional, else the mail's own)"
        />
      </template>
      <template v-if="action.type === 'keyword'">
        <FieldValue v-model="action.keyword" fallback="">
          <input v-model="action.keyword as string" placeholder="Keyword" />
        </FieldValue>
      </template>
      <FieldValue
        v-if="action.type === 'flag' || action.type === 'keyword'"
        v-model="action.value"
        :fallback="true"
      >
        <select v-model="action.value">
          <option :value="true">set</option>
          <option :value="false">clear</option>
        </select>
      </FieldValue>
      <button
        type="button"
        class="ghost danger"
        title="Remove action"
        @click="model.splice(index, 1)"
      >
        ✕
      </button>
    </div>
    <button type="button" class="add" @click="model.push(make('mark_read'))">+ Add action</button>
  </div>
</template>
