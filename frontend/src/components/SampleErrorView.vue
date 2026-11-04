<script setup lang="ts">
import { onMounted } from 'vue'

// Not linked anywhere: open `/sample-error` to check that errors of both sides reach Sentry or Bugsink.
onMounted(async () => {
  try {
    await fetch('/api/sample-error')
  } catch {
    // expected, the server answers 500 (or 401 while logged out)
  }
  setTimeout(() => {
    throw new Error('frontend sample error for Sentry/Bugsink verification')
  }, 0)
})
</script>

<template>
  <main class="sample-error">
    <h2>Sample error</h2>
    <p>
      The backend and this page just raised an error on purpose, to check the error reporting. It
      should show up in Sentry or Bugsink shortly.
    </p>
  </main>
</template>
