<script setup lang="ts">
import FieldValue from './FieldValue.vue'
import type { Location } from '@/model/types'

const model = defineModel<Location[]>('locations', { required: true })

function add(): void {
  model.value.push({
    account_id: model.value[model.value.length - 1]?.account_id ?? '',
    folder: 'INBOX',
    recursive: false,
  })
}
</script>

<template>
  <div class="model">
    <div v-for="(location, index) in model" :key="index" class="row">
      <FieldValue v-model="location.account_id" fallback="">
        <input
          v-model="location.account_id as string"
          placeholder="Account id (UUID, IMAP_ACCOUNT_ID)"
          class="wide mono"
        />
      </FieldValue>
      <FieldValue v-model="location.folder" fallback="INBOX">
        <input
          v-model="location.folder as string"
          placeholder="Folder"
          title="As the server sends it (modified UTF-7)"
        />
      </FieldValue>
      <FieldValue v-model="location.recursive" :fallback="false">
        <label class="check"
          ><input v-model="location.recursive" type="checkbox" /> subfolders</label
        >
      </FieldValue>
      <button
        type="button"
        class="ghost danger"
        :disabled="model.length <= 1"
        title="Remove location"
        @click="model.splice(index, 1)"
      >
        ✕
      </button>
    </div>
    <button type="button" class="add" @click="add">+ Add location</button>
  </div>
</template>
