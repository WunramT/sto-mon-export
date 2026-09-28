<template>
  <div class="regeln">
    <div class="werkzeuge">
      <v-text-field v-model="a.regelnQ" placeholder="Merkmal suchen" prepend-inner-icon="mdi-magnify" clearable class="suche" aria-label="Merkmal suchen" />
      <v-checkbox-btn v-model="a.regelnNurOffen" label="nur Merkmale mit offenen Fragen" density="compact" />
      <v-checkbox-btn v-if="a.daten?.merkmale" v-model="a.regelnNurMaterial" :label="`nur Merkmale aus ${a.daten.matnr}`" density="compact" />
      <v-spacer />
      <span class="text-2 klein">{{ zusammenfassung }}</span>
    </div>
    <v-progress-linear :active="a.regelnLaedt" indeterminate color="primary" height="2" />
    <div class="inhalt">
      <v-alert v-if="d?.hinweise?.length" type="info" variant="tonal" density="compact" class="mb-3">
        {{ mehrzahl(d.hinweise.length, 'Bedingung ist', 'Bedingungen sind') }} nicht lesbar und nur in SAP lösbar – Liste rechts.
      </v-alert>
      <section v-if="d?.kuerzel?.length" class="mb-4">
        <h3 class="abschnitt-titel">Kürzel ohne Zuordnung ({{ d.kuerzel.length }})</h3>
        <div class="kuerzel">
          <div v-for="k in d.kuerzel" :key="k.alias" class="kuerzel-chip">
            <strong class="mono">{{ k.alias }}</strong>
            <span class="text-2">in {{ mehrzahl(k.stuecklisten, 'Stückliste', 'Stücklisten') }}</span>
            <v-btn size="x-small" variant="tonal" color="primary" @click="ui.oeffne('kuerzel', { alias: k.alias })">Zuordnen</v-btn>
          </div>
        </div>
      </section>
      <div v-if="liste.length" class="regel-liste">
        <MerkmalKarte v-for="m in liste" :key="m.merkmal" :m="m" :hervor="a.fokusMerkmal === m.merkmal" />
      </div>
      <div v-else-if="d" class="leer-hinweis">
        {{ a.regelnNurOffen ? 'Keine Merkmale mit offenen Fragen – Häkchen oben entfernen, um alle zu sehen.' : 'Keine Merkmale gefunden.' }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, watch } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import MerkmalKarte from '@/components/MerkmalKarte.vue'
import { mehrzahl } from '@/utils/texte'

const a = useArbeit()
const ui = useUi()
const d = computed(() => a.regelDaten as any)

const liste = computed(() => {
  let m = d.value ? d.value.merkmale : []
  if (a.regelnNurMaterial && a.daten?.merkmale) {
    const hier = new Set(a.daten.merkmale.map((x: any) => x.merkmal))
    m = m.filter((x: any) => hier.has(x.merkmal))
  }
  return m
})

const zusammenfassung = computed(() => {
  if (!d.value) return ''
  return a.regelnNurOffen
    ? `${mehrzahl(d.value.offen, 'offene Regelfrage', 'offene Regelfragen')}: ${mehrzahl(liste.value.length, 'Merkmal', 'Merkmale')}, ${d.value.kuerzel.length} Kürzel`
    : mehrzahl(liste.value.length, 'Merkmal', 'Merkmale')
})

let t: number | undefined
watch(() => a.regelnQ, () => { clearTimeout(t); t = window.setTimeout(() => a.ladeRegelAnsicht(), 250) })
watch(() => a.regelnNurOffen, () => a.ladeRegelAnsicht())
onMounted(async () => {
  await a.ladeRegelAnsicht()
  if (a.fokusMerkmal) nextTick(() => document.querySelector(`.regel-liste [data-merkmal="${CSS.escape(a.fokusMerkmal!)}"]`)?.scrollIntoView({ block: 'start' }))
})
</script>

<style scoped>
.regeln { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.werkzeuge { display: flex; align-items: center; gap: 12px; padding: 10px 18px; border-bottom: 1px solid var(--linie); flex-wrap: wrap; }
.suche { flex: 0 0 240px; min-width: 200px; }
.werkzeuge :deep(.v-selection-control) { min-height: 32px; }
.inhalt :deep(.v-alert) { font-size: 13px; }
.inhalt { flex: 1; overflow-y: auto; padding: 14px 18px 30px; background: var(--flaeche-2); }
.regel-liste { display: grid; grid-template-columns: repeat(auto-fill, minmax(430px, 1fr)); gap: 0 12px; align-items: start; }
.kuerzel { display: flex; flex-wrap: wrap; gap: 6px; }
.kuerzel-chip { display: inline-flex; align-items: center; gap: 8px; padding: 5px 6px 5px 10px; border: 1px solid var(--linie); border-radius: 8px; background: #fff; font-size: 13px; }
</style>
