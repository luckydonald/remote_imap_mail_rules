<script setup lang="ts">
import { useStore } from '@/model/store'

defineEmits<{ close: [] }>()
const store = useStore()
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal queue-overlay" role="dialog" aria-modal="true" aria-label="Queued changes">
        <h3>Queued changes</h3>
        <p v-if="store.queued.length === 0" class="hint">Nothing waits to be sent.</p>
        <table v-else>
          <thead>
            <tr>
              <th>#</th>
              <th>Kind</th>
              <th>Account</th>
              <th>Folder</th>
              <th>UID</th>
              <th>Payload</th>
              <th>Queued</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in store.queued" :key="entry.id" class="queue-row">
              <td>{{ entry.id }}</td>
              <td>
                {{ entry.kind }}{{ entry.after !== undefined ? ` (after #${entry.after})` : '' }}
              </td>
              <td>{{ entry.accountId }}</td>
              <td>{{ entry.folder }}</td>
              <td>{{ entry.uid }}</td>
              <td>
                {{
                  entry.kind === 'move'
                    ? `to ${entry.target}`
                    : `+${entry.add.join(',') || '-'} −${entry.remove.join(',') || '-'}`
                }}
              </td>
              <td>{{ entry.queuedAt }}</td>
              <td>{{ entry.error ?? '' }}</td>
            </tr>
          </tbody>
        </table>
        <footer>
          <button type="button" @click="$emit('close')">Close</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
