import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@schema': fileURLToPath(new URL('../schemas/rules.schema.json', import.meta.url)),
    },
  },
  // The schema lives one level up, in the backend part of the repo.
  server: { fs: { allow: ['..'] } },
})
