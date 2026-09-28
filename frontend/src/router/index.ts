import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/anmelden', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { oeffentlich: true } },
    { path: '/', name: 'start', component: () => import('@/views/ArbeitsView.vue') },
    { path: '/material/:matnr', name: 'material', component: () => import('@/views/ArbeitsView.vue') },
    { path: '/:pfad(.*)*', redirect: '/' },
  ],
})

let konfigGeladen = false
router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!konfigGeladen) { await auth.ladeKonfig(); konfigGeladen = true }
  if (to.meta.oeffentlich) return true
  if ((auth.authAktiv && !auth.angemeldet) || !auth.name) return { name: 'login', query: to.fullPath !== '/' ? { weiter: to.fullPath } : {} }
  return true
})

export default router
