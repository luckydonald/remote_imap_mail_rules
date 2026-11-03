import { createPinia } from 'pinia'
import { createApp } from 'vue'
import AppShell from './components/AppShell.vue'
import './styles/main.scss'

createApp(AppShell).use(createPinia()).mount('#app')
