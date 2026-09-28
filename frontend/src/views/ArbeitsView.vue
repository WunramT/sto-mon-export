<template>
  <KopfLeiste />
  <v-main class="arbeit-main">
    <div class="innen">
    <LadeBildschirm v-if="!bereit" :info="a.datenstand" :fehler="startFehler" @neu="pruefeDatenstand" />
    <template v-else>
      <EntwurfLeiste />
      <div class="raster" :class="{ 'mit-entwurf': !a.entwurfLeer }">
        <MaterialListe class="spalte links" />
        <section class="spalte mitte" aria-label="Arbeitsbereich">
          <v-tabs v-model="a.ansicht" color="primary" density="comfortable" class="reiter" height="44">
            <v-tab value="stueckliste" prepend-icon="mdi-file-tree-outline">Stückliste</v-tab>
            <v-tab value="regeln" prepend-icon="mdi-tune-variant">
              Regeln
              <v-badge v-if="a.offeneFragen" :content="a.offeneFragen" color="warning" inline class="ml-1" />
            </v-tab>
            <v-tab value="auswirkung" prepend-icon="mdi-compare-horizontal">
              Auswirkung
              <v-badge v-if="!a.entwurfLeer" dot color="deep-purple" inline class="ml-1" />
            </v-tab>
          </v-tabs>
          <div class="ansicht">
            <StuecklisteAnsicht v-if="a.ansicht === 'stueckliste'" />
            <RegelnAnsicht v-else-if="a.ansicht === 'regeln'" />
            <AuswirkungAnsicht v-else />
          </div>
        </section>
        <DetailSpalte class="spalte rechts" />
      </div>
    </template>
    </div>
  </v-main>
  <DialogHost />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import KopfLeiste from '@/components/KopfLeiste.vue'
import LadeBildschirm from '@/components/LadeBildschirm.vue'
import EntwurfLeiste from '@/components/EntwurfLeiste.vue'
import MaterialListe from '@/components/MaterialListe.vue'
import StuecklisteAnsicht from '@/components/StuecklisteAnsicht.vue'
import RegelnAnsicht from '@/components/RegelnAnsicht.vue'
import AuswirkungAnsicht from '@/components/AuswirkungAnsicht.vue'
import DetailSpalte from '@/components/DetailSpalte.vue'
import DialogHost from '@/components/dialoge/DialogHost.vue'

const a = useArbeit()
const ui = useUi()
const route = useRoute()
const router = useRouter()
const startFehler = ref<string | null>(null)
const bereit = computed(() => a.datenstand?.zustand === 'bereit' && a.gestartet)
let timer: number | undefined

async function pruefeDatenstand() {
  clearTimeout(timer)
  try {
    const d = await a.ladeDatenstand()
    startFehler.value = null
    if (d.zustand === 'bereit') {
      if (!a.gestartet) {
        await a.start()
        if (a.startFehler) { startFehler.value = a.startFehler; timer = window.setTimeout(pruefeDatenstand, 5000); return }
        oeffneAusRoute(true)
      }
      return
    }
    a.gestartet = false
    timer = window.setTimeout(pruefeDatenstand, d.zustand === 'laedt' ? 2000 : 10000)
  } catch (e) {
    startFehler.value = (e as Error).message
    timer = window.setTimeout(pruefeDatenstand, 5000)
  }
}

function oeffneAusRoute(erstesSonst = false) {
  const m = route.params.matnr as string | undefined
  if (m) { if (m !== a.matnr) a.oeffneMaterial(m) ; return }
  if (!erstesSonst) return
  const erstes = (a.materialien.find((x) => x.zustand === 'offen' || x.zustand === 'in_arbeit') || a.materialien[0])?.matnr
  if (erstes) router.replace({ name: 'material', params: { matnr: erstes } })
}

watch(() => route.params.matnr, () => { if (bereit.value) oeffneAusRoute() })
watch(() => a.matnr, (m) => { if (m && route.params.matnr !== m) router.push({ name: 'material', params: { matnr: m } }) })

function vorVerlassen(ev: BeforeUnloadEvent) {
  if (a.reviewStand.ungespeichert) { ev.preventDefault(); ev.returnValue = '' }
}

onMounted(() => { pruefeDatenstand(); window.addEventListener('beforeunload', vorVerlassen) })
onBeforeUnmount(() => { clearTimeout(timer); window.removeEventListener('beforeunload', vorVerlassen) })

// Neu-Laden aus dem Datenstand-Dialog: Status verfolgen
watch(() => a.datenstand?.zustand, (z, alt) => {
  if (z === 'laedt' && alt === 'bereit') { a.gestartet = false; pruefeDatenstand() }
  if (z === 'bereit' && alt === 'laedt') ui.melde('Datenstand aktualisiert.')
})
</script>

<style scoped>
.arbeit-main { height: 100vh; }
.innen { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.raster { flex: 1; min-height: 0; display: grid; grid-template-columns: 300px minmax(0, 1fr) 400px; }
.spalte { min-height: 0; overflow: hidden; display: flex; flex-direction: column; background: var(--flaeche); }
.links { border-right: 1px solid var(--linie); }
.rechts { border-left: 1px solid var(--linie); background: var(--flaeche-2); }
.mitte { background: var(--flaeche); }
.reiter { border-bottom: 1px solid var(--linie); flex: none; }
.reiter :deep(.v-tab) { text-transform: none; letter-spacing: 0; font-weight: 550; }
.ansicht { flex: 1; min-height: 0; display: flex; flex-direction: column; }
@media (max-width: 1400px) { .raster { grid-template-columns: 260px minmax(0, 1fr) 360px; } }
@media (max-width: 1150px) { .raster { grid-template-columns: 230px minmax(0, 1fr) 320px; } }
</style>
