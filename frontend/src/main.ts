import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/inter'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import './styles/main.scss'
import { verbindeAuth } from './api/client'
import { useAuth } from './stores/auth'
import { useArbeit } from './stores/arbeit'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const auth = useAuth(pinia)
verbindeAuth(() => auth.token, () => {
  auth.abmelden()
  const r = router.currentRoute.value
  if (r.name !== 'login') router.replace({ name: 'login', query: { abgelaufen: '1', ...(r.fullPath !== '/' ? { weiter: r.fullPath } : {}) } })
}, () => {
  // 503 mitten in der Arbeit (z. B. jemand lädt die Exporte neu): Datenstand holen → Ladebildschirm
  useArbeit(pinia).ladeDatenstand().catch(() => {})
})

app.use(router)
app.use(vuetify)
app.mount('#app')
