<script setup lang="ts">
import { ref } from 'vue'
import { ApiError } from '@/model/http'
import { login } from '@/model/mail-api'

const emit = defineEmits<{ loggedIn: [] }>()

const username = ref('')
const password = ref('')
const message = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  busy.value = true
  message.value = ''
  try {
    await login(username.value, password.value)
    password.value = ''
    emit('loggedIn')
  } catch (error) {
    message.value =
      error instanceof ApiError
        ? error.messages.join('; ')
        : `Could not reach the server: ${error instanceof Error ? error.message : String(error)}`
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="login" @submit.prevent="submit">
    <h2>Log in</h2>
    <p class="hint">Log in with the administrator username and password of this server.</p>
    <label>
      Username
      <input v-model="username" name="username" autocomplete="username" required />
    </label>
    <label>
      Password
      <input
        v-model="password"
        name="password"
        type="password"
        autocomplete="current-password"
        required
      />
    </label>
    <p v-if="message" class="message error" role="alert">{{ message }}</p>
    <button type="submit" :disabled="busy">Log in</button>
  </form>
</template>
