<script setup lang="ts">
defineProps<{ count: number }>()
defineEmits<{ send: []; logout: []; cancel: [] }>()
</script>

<template>
  <!-- Out of the scrolling panes: Safari on an iPad clips a fixed dialog to the pane that holds it. -->
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('cancel')">
      <div class="modal" role="dialog" aria-modal="true" aria-label="Unsent changes">
        <h3>Unsent changes</h3>
        <p>
          {{ count }} {{ count === 1 ? 'change has' : 'changes have' }} not been sent to the server
          yet. Logging out now throws {{ count === 1 ? 'it' : 'them' }} away.
        </p>
        <footer>
          <button type="button" class="ghost" @click="$emit('cancel')">Cancel</button>
          <button type="button" class="ghost danger" @click="$emit('logout')">
            Log out anyway
          </button>
          <button type="button" class="keep" @click="$emit('send')">Send, then log out</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
