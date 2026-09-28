<template>
  <v-main class="login-hintergrund">
    <div class="login-rahmen">
      <div class="marke mb-6">
        <div class="logo" aria-hidden="true"><v-icon icon="mdi-file-tree-outline" size="26" color="white" /></div>
        <div>
          <div class="titel">{{ auth.appName }}</div>
          <div class="untertitel">Basis-Stückliste · Prototyp für den Fachbereich</div>
        </div>
      </div>

      <v-card class="pa-7" elevation="0" border>
        <h1 class="text-h6 mb-1">{{ nurName ? 'Wie heißen Sie?' : 'Anmelden' }}</h1>
        <p class="text-body-2 text-2 mb-6">
          <template v-if="nurName">Ihr Name wird bei Regeländerungen und Bewertungen gespeichert, damit nachvollziehbar ist, wer was entschieden hat.</template>
          <template v-else>Mit dem Team-Passwort, das Sie per Mail bekommen haben. Ihr Name wird bei Regeländerungen und Bewertungen gespeichert.</template>
        </p>

        <v-alert v-if="route.query.abgelaufen" type="info" variant="tonal" density="compact" class="mb-4">
          Ihre Sitzung ist abgelaufen – bitte erneut anmelden. Entwurf und ungespeicherte Bewertungen bleiben erhalten.
        </v-alert>

        <v-form @submit.prevent="absenden">
          <label class="feld-label" for="name">Ihr Name</label>
          <v-text-field id="name" v-model="name" placeholder="Vorname Nachname" autocomplete="name" :autofocus="!name" class="mb-4"
            :error-messages="fehlerName" @update:model-value="fehlerName = ''" />
          <template v-if="!nurName">
            <label class="feld-label" for="passwort">Team-Passwort</label>
            <v-text-field id="passwort" v-model="passwort" :type="zeigen ? 'text' : 'password'" autocomplete="current-password"
              :autofocus="Boolean(name)" :append-inner-icon="zeigen ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
              :error-messages="fehler" @click:append-inner="zeigen = !zeigen" @update:model-value="fehler = ''" />
          </template>
          <v-btn type="submit" color="primary" size="large" block class="mt-6" :loading="laedt">
            {{ nurName ? 'Weiter' : 'Anmelden' }}
          </v-btn>
        </v-form>
      </v-card>
      <p class="text-caption text-3 mt-4 text-center">Version {{ auth.version || '–' }} · Nur für den internen Gebrauch</p>
    </div>
  </v-main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const name = ref(auth.name)
const passwort = ref('')
const zeigen = ref(false)
const laedt = ref(false)
const fehler = ref('')
const fehlerName = ref('')
const nurName = computed(() => !auth.authAktiv || auth.angemeldet)

async function absenden() {
  if (!name.value.trim()) { fehlerName.value = 'Bitte Ihren Namen eintragen.'; return }
  if (!nurName.value && !passwort.value) { fehler.value = 'Bitte das Team-Passwort eingeben.'; return }
  laedt.value = true
  try {
    if (!nurName.value || !auth.angemeldet) await auth.anmelden(passwort.value)
    const wechsel = auth.name && auth.name !== name.value.trim()
    auth.setzeName(name.value)
    const weiter = typeof route.query.weiter === 'string' && route.query.weiter.startsWith('/') ? route.query.weiter : '/'
    // andere Person am selben Browser: ohne Reste der vorherigen Sitzung starten
    if (wechsel) window.location.assign(router.resolve(weiter).href)
    else await router.replace(weiter)
  } catch (e) {
    fehler.value = (e as Error).message
  } finally {
    laedt.value = false
  }
}
</script>

<style scoped>
.login-hintergrund { background: linear-gradient(160deg, #eef0f3 0%, #f7f8fa 55%, #fbeef1 100%); min-height: 100vh; }
.login-rahmen { max-width: 440px; margin: 0 auto; padding: 12vh 20px 40px; }
.marke { display: flex; align-items: center; gap: 14px; }
.logo { width: 44px; height: 44px; border-radius: 11px; background: #ce003c; display: grid; place-items: center; box-shadow: 0 6px 16px rgba(206, 0, 60, .25); }
.titel { font-size: 18px; font-weight: 650; letter-spacing: -0.01em; }
.untertitel { font-size: 13px; color: var(--text-2); }
.feld-label { display: block; font-size: 13px; font-weight: 550; margin-bottom: 6px; }
</style>
