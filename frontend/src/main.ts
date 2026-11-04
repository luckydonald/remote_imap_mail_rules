import { createPinia } from 'pinia'
import { createApp } from 'vue'
import AppShell from './components/AppShell.vue'
import { createAppRouter } from './router'
import { setUpSentry } from './sentry'
import './styles/main.scss'

const app = createApp(AppShell)
const router = createAppRouter()
app.use(createPinia()).use(router).mount('#app')
void setUpSentry(app, router)
