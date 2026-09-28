<template>
  <aside aria-label="Materialien">
    <div class="kopf">
      <v-text-field v-model="a.materialQ" placeholder="Nummer oder Text suchen" prepend-inner-icon="mdi-magnify" clearable
        aria-label="Materialien durchsuchen" data-test="material-suche" />
      <div class="filter" role="group" aria-label="Filter nach Bearbeitungsstand">
        <button v-for="f in filterListe" :key="f.wert" type="button" class="filter-knopf" :class="{ aktiv: a.zustandFilter === f.wert }"
          :aria-pressed="a.zustandFilter === f.wert" @click="a.zustandFilter = f.wert">
          {{ f.text }} <span class="zahl">{{ f.anzahl }}</span>
        </button>
      </div>
    </div>
    <div class="liste-rahmen">
      <v-progress-linear v-if="a.materialienLaden && !a.materialien.length" indeterminate color="primary" />
      <v-virtual-scroll v-if="liste.length" :items="liste" item-height="62" class="liste">
        <template #default="{ item: m }">
          <button type="button" class="material" :class="{ aktiv: m.matnr === a.matnr }" :aria-current="m.matnr === a.matnr ? 'true' : undefined"
            :data-matnr="m.matnr" @click="a.oeffneMaterial(m.matnr)">
            <div class="zeile1">
              <span class="nr mono">{{ m.matnr }}</span>
              <span class="zustand" :class="`z-${m.zustand}`">
                <v-icon :icon="ZUSTAND[m.zustand].icon" size="12" /> {{ ZUSTAND[m.zustand].text }}
              </span>
            </div>
            <div class="text" :title="m.kurztext || m.grund || ''">{{ m.kurztext || m.grund || '–' }}</div>
          </button>
        </template>
      </v-virtual-scroll>
      <div v-else-if="!a.materialienLaden" class="leer-hinweis">Keine Materialien gefunden.</div>
    </div>
    <div class="fuss text-3">{{ liste.length }} von {{ a.materialien.length }} Root-Materialien</div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { ZUSTAND } from '@/utils/texte'

const a = useArbeit()

const filterListe = computed(() => {
  const z: Record<string, number> = { alle: a.materialien.length }
  for (const m of a.materialien) z[m.zustand] = (z[m.zustand] || 0) + 1
  return ['alle', 'offen', 'in_arbeit', 'bestaetigt', 'bestaetigt_veraltet', 'nicht_aufloesbar']
    .filter((w) => w === 'alle' || z[w] || a.zustandFilter === w)
    .map((w) => ({ wert: w, text: w === 'alle' ? 'Alle' : ZUSTAND[w].text, anzahl: z[w] || 0 }))
})

const liste = computed(() => {
  const q = (a.materialQ || '').trim().toUpperCase()
  return a.materialien.filter((m) => (a.zustandFilter === 'alle' || m.zustand === a.zustandFilter) &&
    (!q || m.matnr.includes(q) || (m.kurztext || '').toUpperCase().includes(q)))
})
</script>

<style scoped>
.kopf { padding: 12px 12px 8px; border-bottom: 1px solid var(--linie); flex: none; }
.filter { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 10px; }
.filter-knopf { border: 1px solid var(--linie-2); background: #fff; border-radius: 999px; padding: 3px 9px; font-size: 12px; color: var(--text-2); cursor: pointer; }
.filter-knopf:hover { background: var(--hover); }
.filter-knopf.aktiv { background: var(--text-1); border-color: var(--text-1); color: #fff; }
.filter-knopf .zahl { opacity: .7; margin-left: 2px; }
.liste-rahmen { flex: 1; min-height: 0; }
.liste { height: 100%; }
.material { display: block; width: 100%; text-align: left; padding: 10px 14px; border: 0; border-bottom: 1px solid var(--linie); background: transparent; cursor: pointer; height: 62px; border-left: 3px solid transparent; }
.material:hover { background: var(--hover); }
.material.aktiv { background: var(--auswahl); border-left-color: var(--auswahl-rand); }
.zeile1 { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.nr { font-weight: 650; font-size: 14px; }
.text { font-size: 12.5px; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 3px; }
.zustand { font-size: 11px; font-weight: 550; display: inline-flex; align-items: center; gap: 3px; padding: 1px 7px; border-radius: 999px; }
.z-offen { color: var(--s-unbedingt); background: var(--s-unbedingt-bg); }
.z-in_arbeit { color: var(--s-manuell); background: var(--s-manuell-bg); }
.z-bestaetigt { color: var(--s-basis); background: var(--s-basis-bg); }
.z-bestaetigt_veraltet { color: #8a4b00; background: #fde9c8; }
.z-nicht_aufloesbar { color: var(--s-aus); background: var(--s-aus-bg); }
.fuss { flex: none; font-size: 11.5px; padding: 6px 14px; border-top: 1px solid var(--linie); }
</style>
