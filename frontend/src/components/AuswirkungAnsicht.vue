<template>
  <div class="auswirkung">
    <div v-if="a.entwurfLeer" class="leer-hinweis">
      <v-icon icon="mdi-compare-horizontal" size="40" class="mb-2 text-3" />
      <p class="text-body-1 mb-1">Kein Entwurf offen.</p>
      <p class="text-body-2">Ändern Sie eine Regel (Status oder Rang) – hier sehen Sie dann, welche Materialien sich dadurch ändern.</p>
    </div>
    <div v-else-if="a.auswirkungLaedt && !w" class="leer-hinweis">
      <v-progress-circular indeterminate color="primary" class="mb-3" />
      <p>Rechne alle betroffenen Materialien neu …</p>
    </div>
    <div v-else-if="w?.fehler" class="leer-hinweis">{{ w.fehler }}</div>
    <template v-else-if="w">
      <div class="kopf">
        <div>
          <h2 class="titel">{{ w.betroffen ? `Ihr Entwurf ändert ${mehrzahl(w.betroffen, 'Material', 'Materialien')}` : 'Ihr Entwurf ändert keine Stückliste' }}</h2>
          <p class="text-2 klein mb-0">{{ mehrzahl(w.geprueft, 'Material enthält', 'Materialien enthalten') }} die geänderten Merkmale und {{ w.geprueft === 1 ? 'wurde' : 'wurden' }} neu gerechnet.</p>
        </div>
        <v-btn size="small" variant="outlined" prepend-icon="mdi-refresh" :loading="a.auswirkungLaedt" @click="a.berechneAuswirkung()">Neu berechnen</v-btn>
      </div>
      <v-table v-if="w.materialien.length" density="comfortable" class="tabelle" fixed-header height="100%">
        <thead>
          <tr><th>Material</th><th>Geänderte Positionen</th><th>In der Basis-Stückliste</th><th>Beispiele</th></tr>
        </thead>
        <tbody>
          <tr v-for="m in w.materialien" :key="m.matnr" class="klickbar" title="Material mit Entwurf öffnen" @click="a.oeffneMaterial(m.matnr)">
            <td><strong class="mono">{{ m.matnr }}</strong><div class="text-2 klein">{{ m.kurztext }}</div></td>
            <td>
              <div v-for="(x, i) in m.wechsel" :key="i" class="wechsel">
                <span class="mono">{{ x.anzahl }}×</span>
                <span v-if="x.von" class="st" :class="`st-${x.von}`"><span class="pkt" />{{ STATUS[x.von]?.kurz }}</span><span v-else class="text-3">neu</span>
                <v-icon icon="mdi-arrow-right" size="14" class="text-3" />
                <span v-if="x.nach" class="st" :class="`st-${x.nach}`"><span class="pkt" />{{ STATUS[x.nach]?.kurz }}</span><span v-else class="text-3">entfällt</span>
              </div>
            </td>
            <td class="mono">{{ m.vorher_im_ergebnis }} <v-icon icon="mdi-arrow-right" size="14" class="text-3" /> <strong>{{ m.nachher_im_ergebnis }}</strong>
              <span :class="m.nachher_im_ergebnis > m.vorher_im_ergebnis ? 'plus' : m.nachher_im_ergebnis < m.vorher_im_ergebnis ? 'minus' : 'text-3'">
                ({{ m.nachher_im_ergebnis - m.vorher_im_ergebnis >= 0 ? '+' : '' }}{{ m.nachher_im_ergebnis - m.vorher_im_ergebnis }})
              </span>
            </td>
            <td><div v-for="(b, i) in m.beispiele" :key="i" class="klein text-2"><span class="mono">{{ b.matnr }}</span> {{ b.kurztext }}</div></td>
          </tr>
        </tbody>
      </v-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { STATUS, mehrzahl } from '@/utils/texte'

const a = useArbeit()
const w = computed(() => a.auswirkung as any)
onMounted(() => { if (!a.entwurfLeer && !a.auswirkung) a.berechneAuswirkung() })
</script>

<style scoped>
.auswirkung { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.kopf { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 16px 18px; border-bottom: 1px solid var(--linie); }
.titel { font-size: 17px; font-weight: 700; margin: 0 0 2px; }
.tabelle { flex: 1; min-height: 0; }
.tabelle th { font-size: 11px !important; text-transform: uppercase; letter-spacing: .05em; color: var(--text-3) !important; }
.klickbar { cursor: pointer; }
.klickbar:hover td { background: var(--hover); }
.wechsel { display: flex; align-items: center; gap: 6px; margin: 2px 0; font-size: 13px; }
.plus { color: var(--s-basis); font-weight: 600; } .minus { color: #b3261e; font-weight: 600; }
td { vertical-align: top; padding-top: 10px !important; padding-bottom: 10px !important; }
</style>
