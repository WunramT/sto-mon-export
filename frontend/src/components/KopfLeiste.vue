<template>
  <v-app-bar color="secondary" density="comfortable" flat height="56">
    <div class="marke">
      <div class="logo" aria-hidden="true"><v-icon icon="mdi-file-tree-outline" size="20" color="white" /></div>
      <div class="min-w-0">
        <div class="titel">{{ auth.appName }}</div>
        <div class="untertitel" data-test="kopf-meta">{{ untertitel }}</div>
      </div>
    </div>
    <v-spacer />
    <v-btn variant="text" color="white" prepend-icon="mdi-database-outline" class="mr-1" data-test="datenstand-knopf"
      @click="ui.oeffne('datenstand')">
      Datenstand
      <v-icon v-if="a.datenstand?.zustand === 'laedt'" icon="mdi-loading mdi-spin" size="16" class="ml-1" />
    </v-btn>
    <v-btn variant="text" color="white" prepend-icon="mdi-help-circle-outline" class="mr-1" @click="ui.oeffne('hilfe')">Hilfe</v-btn>
    <v-menu location="bottom end">
      <template #activator="{ props }">
        <v-btn v-bind="props" variant="tonal" color="white" class="mr-3 nutzer" data-test="nutzer-knopf">
          <v-avatar size="24" color="primary" class="mr-2 text-caption font-weight-bold">{{ kuerzel }}</v-avatar>
          {{ auth.name || 'Name eingeben' }}
          <v-icon icon="mdi-chevron-down" size="18" class="ml-1" />
        </v-btn>
      </template>
      <v-list density="compact" min-width="220">
        <v-list-item prepend-icon="mdi-account-edit-outline" title="Name ändern" @click="ui.oeffne('name')" />
        <v-list-item v-if="auth.authAktiv" prepend-icon="mdi-logout" title="Abmelden" @click="abmelden" />
      </v-list>
    </v-menu>
  </v-app-bar>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useArbeit } from '@/stores/arbeit'
import { useAuth } from '@/stores/auth'
import { useUi } from '@/stores/ui'
import { fmtDatum, mehrzahl } from '@/utils/texte'

const a = useArbeit()
const auth = useAuth()
const ui = useUi()
const router = useRouter()

const kuerzel = computed(() => (auth.name || '?').split(/\s+/).map((t) => t[0]).join('').slice(0, 2).toUpperCase())
const untertitel = computed(() => {
  const m = a.meta
  if (!m) return a.datenstand?.zustand === 'laedt' ? 'Daten werden geladen …' : 'Basis-Stückliste'
  const basis = m.offen ? mehrzahl(m.offen, 'offene Regelfrage', 'offene Regelfragen') : 'keine offenen Regelfragen'
  const mit = !a.entwurfLeer && a.offeneFragen !== m.offen ? ` · mit Ihrem Entwurf: ${a.offeneFragen}` : ''
  return `Datenstand ${fmtDatum(m.stichtag)} · ${basis}${mit}`
})

async function abmelden() {
  if (a.reviewStand.ungespeichert && !(await ui.frage({ titel: 'Abmelden?', text: 'Ungespeicherte Bewertungen bleiben in diesem Browser erhalten und sind nach der nächsten Anmeldung wieder da.', ja: 'Abmelden' }))) return
  auth.abmelden()
  // vollständig neu laden: kein Zustand der vorherigen Person bleibt im Speicher
  window.location.assign(router.resolve({ name: 'login' }).href)
}
</script>

<style scoped>
.marke { display: flex; align-items: center; gap: 12px; padding-left: 16px; min-width: 0; }
.logo { width: 32px; height: 32px; border-radius: 8px; background: #ce003c; display: grid; place-items: center; flex: none; }
.titel { font-size: 15px; font-weight: 650; color: #fff; letter-spacing: -0.01em; line-height: 1.2; }
.untertitel { font-size: 12px; color: rgba(255, 255, 255, .72); line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nutzer { text-transform: none; }
.min-w-0 { min-width: 0; }
</style>
