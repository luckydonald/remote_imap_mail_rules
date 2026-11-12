import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    // The app shell works offline; the mail cache itself lives in IndexedDB (`src/model/offline/`), `/api` is never cached by the worker.
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: false,
      manifest: {
        name: 'Mail Rules Editor',
        short_name: 'Mail rules',
        display: 'standalone',
        start_url: '/',
        icons: [],
      },
      workbox: {
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/assets/],
        globPatterns: ['**/*.{js,css,html,ico,svg,woff2}'],
        runtimeCaching: [],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@schema': fileURLToPath(new URL('../schemas/rules.schema.json', import.meta.url)),
    },
  },
  // The schema lives one level up, in the backend part of the repo.
  // `/api` goes (or to `API_PROXY`, the e2e tests point it at a closed port so a running server cannot interfere) to the FastAPI server (`uv run python -m remote_imap_mail_rules.server.main`) while developing.
  server: {
    fs: { allow: ['..'] },
    proxy: { '/api': process.env.API_PROXY ?? 'http://127.0.0.1:8000' },
  },
})
