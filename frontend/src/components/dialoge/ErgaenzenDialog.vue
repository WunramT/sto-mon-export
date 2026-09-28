<template>
  <v-card>
    <v-card-title class="pt-5 px-6">Fehlendes Material ergänzen</v-card-title>
    <v-card-text class="px-6">
      <v-alert v-if="daten.hinweis" type="info" variant="tonal" density="compact" class="mb-3">{{ daten.hinweis }}</v-alert>
      <p class="text-body-2 text-2 mb-4">Für Materialien, die in die Basis-Stückliste gehören, aber im Baum ganz fehlen.</p>
      <v-select v-model="unter" :items="baugruppen" item-title="text" item-value="id" label="Unter Baugruppe" class="mb-4"
        :messages="a.unterRaus(unter, true) ? 'Diese Baugruppe kommt nicht in die Basis – ein Material darunter käme nicht in den Export.' : ''" :color="a.unterRaus(unter, true) ? 'warning' : undefined" />
      <v-text-field v-model="nr" label="Materialnummer" placeholder="z. B. 10000999" inputmode="numeric" autofocus class="mb-1"
        :messages="info.text" :color="info.farbe" :error-messages="nrFehler" @update:model-value="pruefe" />
      <div class="reihe mt-3">
        <v-text-field v-model.number="menge" label="Menge je Baugruppe" type="number" min="0" step="any" :error-messages="mengeFehler" @update:model-value="mengeFehler = ''" />
        <v-select v-model="einheit" :items="['ST', 'M', 'M2', 'KG', 'L', 'PAA']" label="Einheit" />
        <v-text-field v-model="kommentar" label="Kommentar (optional)" />
      </div>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="abbrechen">Abbrechen</v-btn>
      <v-btn color="primary" @click="ok">Ergänzen</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'

const props = defineProps<{ daten: { parentId: string; hinweis?: string; klasseId?: string } }>()
const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const ui = useUi()
const d = a.daten as any
const baugruppen = computed(() => [
  { id: d.matnr, text: `${d.matnr} ${d.kurztext} (oberste Ebene)` },
  ...d.positionen.filter((p: any) => p.hat_kinder).map((p: any) => ({ id: p.id,
    text: `${'· '.repeat(p.ebene)}${p.matnr} ${p.kurztext}${a.unterRaus(p.id, true) ? ' – nicht in der Basis' : ''}` })),
])
const unter = ref(props.daten.parentId)
const nr = ref('')
const menge = ref<number>(1)
const einheit = ref('ST')
const kommentar = ref('')
const info = ref<{ text: string; farbe?: string }>({ text: '' })
const nrFehler = ref('')
const mengeFehler = ref('')
let geprueft: any = null
let t: number | undefined

function pruefe() {
  clearTimeout(t)
  nrFehler.value = ''
  geprueft = null
  const wert = nr.value.trim()
  info.value = { text: wert ? 'Prüfe …' : '' }
  if (!wert) return
  t = window.setTimeout(async () => {
    try {
      geprueft = await api('GET', `/materialinfo/${encodeURIComponent(wert)}`)
      info.value = geprueft.bekannt ? { text: `✓ ${geprueft.kurztext || 'bekanntes Material'}`, farbe: 'success' }
        : { text: 'Im SAP-Export unbekannt – bitte prüfen (ergänzen ist trotzdem möglich).', farbe: 'warning' }
    } catch { info.value = { text: '' } }
  }, 250)
}

// Klassenposition „rein“ ohne Material ergibt keinen Sinn → beim Abbrechen das „rein“ wieder zurücknehmen
function abbrechen() {
  if (props.daten.klasseId) { a.setzeUrteil(props.daten.klasseId, null); ui.melde('„Sollte rein“ zurückgenommen – ohne Material bleibt die Klassenposition offen.') }
  emit('schliessen')
}

function ok() {
  const wert = nr.value.trim().replace(/^0+/, '')
  if (!wert) { nrFehler.value = 'Bitte eine Materialnummer eintragen.'; return }
  if (!(Number(menge.value) > 0)) { mengeFehler.value = 'Menge größer 0'; return }
  const parent = unter.value === d.matnr ? { matnr: d.matnr } : d.positionen.find((p: any) => p.id === unter.value)
  a.ergaenze({ parent_pfad: unter.value, parent_matnr: parent.matnr, matnr: wert, kurztext: geprueft?.kurztext || '',
    menge: Number(menge.value), meins: einheit.value, kommentar: kommentar.value.trim() || null })
  emit('schliessen')
  ui.melde(`${wert} ergänzt – noch nicht gespeichert.`)
}
</script>

<style scoped>
.reihe { display: grid; grid-template-columns: 150px 100px 1fr; gap: 10px; }
</style>
