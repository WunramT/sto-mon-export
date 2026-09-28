import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import { speicher } from '@/utils/speicher'

export const useAuth = defineStore('auth', () => {
  const token = ref<string | null>(speicher.lies('kse.token', null))
  const ablauf = ref<number>(speicher.lies('kse.ablauf', 0))
  const name = ref<string>(speicher.lies('bb.name', ''))
  const authAktiv = ref(true)
  const appName = ref('Export konfigurierbare Stücklisten')
  const version = ref('')

  const angemeldet = computed(() => Boolean(token.value) && ablauf.value > Date.now())

  async function ladeKonfig() {
    try {
      const k = await api('GET', '/auth/config')
      authAktiv.value = k.auth_aktiv
      appName.value = k.app_name
      version.value = k.version
    } catch { /* Server nicht erreichbar: Login-Seite zeigt den Fehler */ }
  }

  async function anmelden(passwort: string) {
    const r = await api('POST', '/auth/login', { passwort })
    token.value = r.access_token
    ablauf.value = Date.now() + (r.expires_in - 60) * 1000
    speicher.schreib('kse.token', token.value)
    speicher.schreib('kse.ablauf', ablauf.value)
  }

  function abmelden() {
    token.value = null
    ablauf.value = 0
    speicher.entferne('kse.token')
    speicher.entferne('kse.ablauf')
  }

  function setzeName(n: string) {
    name.value = n.trim()
    speicher.schreib('bb.name', name.value)
  }

  return { token, name, authAktiv, appName, version, angemeldet, ladeKonfig, anmelden, abmelden, setzeName }
})
