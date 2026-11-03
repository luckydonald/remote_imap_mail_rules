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
  // `/api` goes (or to `API_PROXY`, the e2e tests point it at a closed port so a running server cannot interfere) to the FastAPI server (`uv run python -m remote_imap_mail_rules.server.main`) while developing.
  server: { fs: { allow: ['..'] }, proxy: { '/api': process.env.API_PROXY ?? 'http://127.0.0.1:8000' } },
})
