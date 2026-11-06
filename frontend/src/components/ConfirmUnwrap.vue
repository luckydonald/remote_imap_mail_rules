<script setup lang="ts">
defineProps<{ count: number }>()
defineEmits<{ keep: []; remove: []; cancel: [] }>()
</script>

<template>
  <!-- Out of the scrolling panes: Safari on an iPad clips a fixed dialog to the pane that holds it. -->
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="$emit('cancel')">
      <div class="modal" role="dialog" aria-modal="true" aria-label="Remove group">
        <h3>Remove this group?</h3>
        <p>
          It holds {{ count }} {{ count === 1 ? 'condition' : 'conditions' }}. Keep them in its
          place?
        </p>
        <footer>
          <button type="button" class="ghost" @click="$emit('cancel')">Cancel</button>
          <button type="button" class="ghost danger" @click="$emit('remove')">Remove all</button>
          <button type="button" class="keep" @click="$emit('keep')">Keep the children</button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
