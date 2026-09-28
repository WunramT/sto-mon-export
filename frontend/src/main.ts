import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/inter'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import './styles/main.scss'
import { verbindeAuth } from './api/client'
import { useAuth } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const auth = useAuth(pinia)
verbindeAuth(() => auth.token, () => {
  auth.abmelden()
  if (router.currentRoute.value.name !== 'login') router.replace({ name: 'login', query: { abgelaufen: '1' } })
})

app.use(router)
app.use(vuetify)
app.mount('#app')
