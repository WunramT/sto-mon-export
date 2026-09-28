<template>
  <div class="lade-rahmen">
    <v-card class="pa-8 lade-karte" elevation="0" border>
      <template v-if="fehler && !info">
        <v-icon icon="mdi-lan-disconnect" size="40" color="error" class="mb-3" />
        <h1 class="text-h6 mb-2">Server nicht erreichbar</h1>
        <p class="text-body-2 text-2 mb-5">{{ fehler }}<br>Die Seite versucht es automatisch weiter.</p>
        <v-btn color="primary" variant="tonal" @click="$emit('neu')">Jetzt erneut versuchen</v-btn>
      </template>

      <template v-else-if="!info || info.zustand === 'laedt' || (info.zustand === 'bereit')">
        <v-progress-circular indeterminate color="primary" size="44" width="4" class="mb-4" />
        <h1 class="text-h6 mb-1">Daten werden geladen …</h1>
        <p class="text-body-2 text-2 mb-5">
          <template v-if="info?.quelle === 'exporte'">Die SAP-Exporte werden eingelesen. Mit der großen STPO-Datei dauert das einige Minuten – die Seite geht danach von selbst weiter.</template>
          <template v-else>Einen Moment bitte.</template>
        </p>
        <ol v-if="info?.schritte?.length" class="schritte">
          <li v-for="(s, i) in info.schritte" :key="i" :class="{ aktiv: i === info.schritte.length - 1 && info.zustand === 'laedt' }">
            <v-icon :icon="i === info.schritte.length - 1 && info.zustand === 'laedt' ? 'mdi-loading mdi-spin' : 'mdi-check'" size="16" />
            {{ s }}
          </li>
        </ol>
        <p v-if="info?.gestartet" class="text-caption text-3 mt-4">Gestartet {{ fmtZeit(info.gestartet) }}</p>
      </template>

      <template v-else-if="info.zustand === 'leer'">
        <v-icon icon="mdi-database-off-outline" size="40" color="warning" class="mb-3" />
        <h1 class="text-h6 mb-2">Noch keine Daten</h1>
        <p class="text-body-2 text-2 mb-2">{{ info.meldung }}</p>
        <p class="text-body-2 text-2 mb-5">Die SAP-Exporte müssen im Export-Verzeichnis auf dem Server liegen (Ansprechpartner: das Projektteam). Danach hier laden.</p>
        <v-btn color="primary" :loading="startet" @click="neuLaden">Exporte laden</v-btn>
      </template>

      <template v-else>
        <v-icon icon="mdi-alert-circle-outline" size="40" color="error" class="mb-3" />
        <h1 class="text-h6 mb-2">Laden fehlgeschlagen</h1>
        <v-alert type="error" variant="tonal" density="compact" class="mb-4 text-left" style="white-space: pre-wrap">{{ info.fehler }}</v-alert>
        <p class="text-body-2 text-2 mb-5">Exporte prüfen (Dateinamen, Spalten) und erneut laden. Details stehen im Log des Backends.</p>
        <v-btn color="primary" :loading="startet" @click="neuLaden">Erneut laden</v-btn>
      </template>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'
import { useUi } from '@/stores/ui'
import { fmtZeit } from '@/utils/texte'

defineProps<{ info: any; fehler: string | null }>()
const emit = defineEmits<{ neu: [] }>()
const ui = useUi()
const startet = ref(false)

async function neuLaden() {
  startet.value = true
  try { await api('POST', '/datenstand/neu-laden'); emit('neu') } catch (e) { ui.melde((e as Error).message, true) } finally { startet.value = false }
}
</script>

<style scoped>
.lade-rahmen { flex: 1; display: grid; place-items: center; padding: 24px; background: var(--flaeche-2); }
.lade-karte { max-width: 520px; width: 100%; text-align: center; }
.schritte { list-style: none; padding: 0; margin: 0 auto; display: inline-flex; flex-direction: column; gap: 6px; text-align: left; font-size: 13px; color: var(--text-2); }
.schritte li { display: flex; align-items: center; gap: 8px; }
.schritte li.aktiv { color: var(--text-1); font-weight: 550; }
</style>
