<template>
  <v-card>
    <v-card-title class="pt-5 px-6 d-flex align-center">
      Datenstand
      <v-spacer />
      <v-chip :color="farbe" size="small" variant="flat">{{ zustandText }}</v-chip>
    </v-card-title>
    <v-card-text class="px-6">
      <dl class="kv mb-4">
        <dt>Stichtag</dt><dd>{{ fmtDatum(info?.stichtag) }}</dd>
        <dt>Quelle</dt><dd>{{ QUELLE[info?.quelle] || '–' }}</dd>
        <dt>Zuletzt geladen</dt><dd>{{ info?.beendet ? `${fmtZeit(info.beendet)} (${info.dauer_s} s)` : info?.quelle === 'datenbank' ? 'vor dem letzten Neustart' : '–' }}</dd>
        <dt>Export-Verzeichnis</dt><dd class="mono">{{ info?.exports_dir }}</dd>
      </dl>
      <v-alert v-if="info?.zustand === 'laedt'" type="info" variant="tonal" density="compact" class="mb-3">
        Lädt: {{ info.schritt }} (gestartet {{ fmtZeit(info.gestartet) }})
      </v-alert>
      <v-alert v-if="info?.fehler" type="error" variant="tonal" density="compact" class="mb-3" style="white-space: pre-wrap">{{ info.fehler }}</v-alert>
      <v-alert v-for="w in info?.warnungen || []" :key="w" type="warning" variant="tonal" density="compact" class="mb-2">{{ w }}</v-alert>

      <h3 class="abschnitt-titel mt-2">Dateien im Export-Verzeichnis ({{ info?.dateien?.length || 0 }})</h3>
      <v-table v-if="info?.dateien?.length" density="compact" class="dateien">
        <thead><tr><th>Datei</th><th class="text-right">Größe</th><th>Geändert</th></tr></thead>
        <tbody>
          <tr v-for="f in info.dateien" :key="f.name"><td class="mono">{{ f.name }}</td><td class="text-right mono">{{ fmtGroesse(f.groesse) }}</td><td>{{ fmtZeit(f.geaendert) }}</td></tr>
        </tbody>
      </v-table>
      <p v-else class="text-body-2 text-2">Keine Dateien. Exporte auf dem Server in das Verzeichnis legen (Liste in <code>docs/EXPORTE.md</code>).</p>
      <p class="text-caption text-2 mt-4 mb-0">„Neu laden“ ersetzt die SAP-Daten in der Datenbank. Regeln, Bewertungen und Bestätigungen bleiben erhalten. Während des Ladens (mit STPO einige Minuten) ist die Oberfläche für alle gesperrt.</p>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-btn variant="text" prepend-icon="mdi-refresh" @click="lade">Aktualisieren</v-btn>
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Schließen</v-btn>
      <v-btn color="primary" prepend-icon="mdi-database-refresh-outline" :disabled="!info?.dateien?.length || info?.zustand === 'laedt'" :loading="startet" @click="neuLaden">Exporte neu laden</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import { fmtDatum, fmtGroesse, fmtZeit } from '@/utils/texte'

const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const ui = useUi()
const startet = ref(false)
const info = computed(() => a.datenstand as any)
const QUELLE: Record<string, string> = { exporte: 'SAP-Exporte', beispieldaten: 'Beispieldaten (Demo)', datenbank: 'Datenbank (bereits geladen)' }
const zustandText = computed(() => ({ bereit: 'bereit', laedt: 'lädt …', fehler: 'Fehler', leer: 'keine Daten' } as Record<string, string>)[info.value?.zustand] || '–')
const farbe = computed(() => ({ bereit: 'success', laedt: 'info', fehler: 'error', leer: 'warning' } as Record<string, string>)[info.value?.zustand] || 'grey')

async function lade() { try { await a.ladeDatenstand() } catch (e) { ui.melde((e as Error).message, true) } }
onMounted(lade)

async function neuLaden() {
  const ok = await ui.frage({ titel: 'Exporte neu laden?', text: 'Die SAP-Daten werden aus dem Export-Verzeichnis neu eingelesen. Während des Ladens können weder Sie noch Ihre Kolleg:innen arbeiten. Regeln und Bewertungen bleiben erhalten.', ja: 'Neu laden' })
  if (!ok) return
  startet.value = true
  try {
    a.datenstand = await api('POST', '/datenstand/neu-laden')
    emit('schliessen')
  } catch (e) { ui.melde((e as Error).message, true) } finally { startet.value = false }
}
</script>

<style scoped>
.kv { display: grid; grid-template-columns: 150px 1fr; gap: 4px 12px; font-size: 13.5px; margin: 0; }
.kv dt { color: var(--text-2); }
.kv dd { margin: 0; word-break: break-all; }
.dateien { font-size: 12.5px; border: 1px solid var(--linie); border-radius: 8px; }
</style>
