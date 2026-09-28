<template>
  <v-card v-if="!konflikte">
    <v-card-title class="pt-5 px-6">Regeländerungen übernehmen</v-card-title>
    <v-card-text class="px-6">
      <p class="text-body-2 mb-2">{{ a.entwurfAnzahl === 1 ? 'Diese Änderung gilt' : `Diese ${a.entwurfAnzahl} Änderungen gelten` }} danach für alle Materialien und alle Kolleg:innen:</p>
      <ul class="liste mb-4">
        <li v-for="e in a.entwurfListe" :key="e.alias || `${e.merkmal}|${e.wert}`">{{ a.entwurfEintragText(e) }}</li>
      </ul>
      <v-textarea v-model="begruendung" label="Begründung (Pflicht, für die Historie)" rows="3" autofocus
        placeholder="z. B. „Laut Produktmanagement ist FK die Standardausführung“"
        :messages="begruendung.trim().length < 5 ? 'Mindestens 5 Zeichen – andere sollen die Entscheidung nachvollziehen können.' : ''" />
      <p class="text-caption text-2 mt-3 mb-0">Gespeichert als: {{ auth.name }}</p>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Abbrechen</v-btn>
      <v-btn color="deep-purple" :disabled="begruendung.trim().length < 5" :loading="laedt" data-test="uebernehmen-ok" @click="ok">Übernehmen</v-btn>
    </v-card-actions>
  </v-card>

  <v-card v-else>
    <v-card-title class="pt-5 px-6">Jemand hat diese Regeln inzwischen geändert</v-card-title>
    <v-card-text class="px-6">
      <p class="text-body-2 mb-2">Seit Sie angefangen haben, wurden folgende Werte von jemand anderem geändert:</p>
      <ul class="liste mb-3">
        <li v-for="(k, i) in konflikte" :key="i">
          <template v-if="k.art === 'regel'">{{ a.mName(k.merkmal) }} = {{ k.wert }}: jetzt {{ REGEL_STATUS[k.jetzt.status] }}<template v-if="k.jetzt.rang"> (Rang {{ k.jetzt.rang }})</template></template>
          <template v-else>Kürzel {{ k.alias }}: jetzt {{ k.jetzt.merkmal ? a.mName(k.jetzt.merkmal) : 'ohne Merkmal' }}</template>
        </li>
      </ul>
      <p class="text-body-2">Laden Sie den aktuellen Stand: Ihre übrigen Änderungen bleiben im Entwurf, die betroffenen Werte können Sie danach neu setzen.</p>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn color="primary" @click="aufloesen">Aktuellen Stand laden</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ApiFehler } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { useAuth } from '@/stores/auth'
import { useUi } from '@/stores/ui'
import { REGEL_STATUS } from '@/utils/texte'

const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const auth = useAuth()
const ui = useUi()
const begruendung = ref('')
const laedt = ref(false)
const konflikte = ref<any[] | null>(null)

async function ok() {
  laedt.value = true
  try {
    await a.uebernehmen(begruendung.value.trim())
    emit('schliessen')
  } catch (e) {
    if (e instanceof ApiFehler && e.status === 409) konflikte.value = e.daten.konflikte
    else ui.melde((e as Error).message, true)
  } finally {
    laedt.value = false
  }
}

async function aufloesen() {
  await a.konfliktAufloesen(konflikte.value || [])
  emit('schliessen')
}
</script>

<style scoped>
.liste { padding-left: 18px; font-size: 13.5px; line-height: 1.6; }
</style>
