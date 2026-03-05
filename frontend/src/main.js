import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const GLOBAL_FONT_STORAGE_KEY = 'global_font_preference_v1'
const initialFont = localStorage.getItem(GLOBAL_FONT_STORAGE_KEY)
document.documentElement.setAttribute(
  'data-global-font',
  initialFont === 'heiti' ? 'heiti' : 'default'
)

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
