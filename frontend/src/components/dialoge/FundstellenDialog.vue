<template>
  <v-card>
    <v-card-title class="pt-5 px-6">
      Wo kommt <span class="mono">{{ titel }}</span> vor?
      <div class="text-body-2 text-2">Einfluss des Werts: Beziehungswissen, Stücklisten und Modelle{{ a.entwurfLeer ? '' : ' (mit Ihrem Entwurf)' }}</div>
    </v-card-title>
    <v-card-text class="px-6">
      <v-progress-linear v-if="laedt" indeterminate color="primary" class="mb-3" />
      <v-alert v-if="fehler" type="error" variant="tonal" density="compact">{{ fehler }}</v-alert>
      <template v-if="f">
        <div class="zahlen mb-4">
          <div><strong class="mono">{{ f.anzahl.beziehungen }}</strong><span>Beziehungswissen</span></div>
          <div><strong class="mono">{{ f.anzahl.stuecklisten }}</strong><span>{{ f.anzahl.stuecklisten === 1 ? 'Stückliste' : 'Stücklisten' }}</span></div>
          <div><strong class="mono">{{ f.anzahl.modelle }}</strong><span>{{ f.anzahl.modelle === 1 ? 'Modell' : 'Modelle' }}</span></div>
        </div>
        <v-alert v-if="!f.anzahl.stuecklisten" type="info" variant="tonal" density="compact" icon="mdi-database-off-outline">
          Dieser Wert kommt in den geladenen SAP-Daten in keiner Auswahlbedingung vor – vermutlich eine Startregel.
          Die Entscheidung wirkt derzeit auf kein Material.
        </v-alert>
        <template v-else>
          <v-tabs v-model="reiter" density="compact" color="primary" class="mb-3">
            <v-tab value="beziehungen">Beziehungswissen ({{ f.anzahl.beziehungen }})</v-tab>
            <v-tab value="modelle">Betroffene Modelle ({{ f.anzahl.modelle }})</v-tab>
          </v-tabs>

          <div v-if="reiter === 'beziehungen'">
            <v-expansion-panels v-model="offen" multiple variant="accordion">
              <v-expansion-panel v-for="b in f.beziehungen" :key="b.knnum" :value="b.knnum">
                <v-expansion-panel-title>
                  <div class="bw-kopf">
                    <code class="knnam">{{ b.knnam }}</code>
                    <span class="text-3 klein mono">KNNUM {{ b.knnum }}</span>
                    <v-spacer />
                    <span class="text-2 klein">{{ mehrzahl(b.anzahl, 'Stückliste', 'Stücklisten') }}</span>
                    <QuelltextAnzeige class="bw-text" :text="b.text" />
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-table density="compact" class="tabelle">
                    <thead><tr><th>Stückliste</th><th>Kopfmaterial</th><th>Position (Komponente)</th></tr></thead>
                    <tbody>
                      <tr v-for="s in b.stuecklisten" :key="s.stlnr">
                        <td class="mono">{{ s.stlnr }}</td>
                        <td>
                          <div v-for="k in s.kopf" :key="k.matnr">
                            <button v-if="k.root" type="button" class="link mono" title="Material öffnen" @click="oeffne(k.matnr)">{{ k.matnr }}</button>
                            <span v-else class="mono">{{ k.matnr }}</span>
                            <span class="text-2 zusatz">{{ k.kurztext }}</span>
                          </div>
                          <span v-if="!s.kopf.length" class="text-3">kein Kopfmaterial (Werk 4000)</span>
                        </td>
                        <td>
                          <div v-for="(p, i) in s.positionen" :key="i"><span class="mono">{{ p.posnr }}</span> · <span class="mono">{{ p.matnr || 'ohne Material' }}</span><span class="text-2 zusatz">{{ p.kurztext }}</span></div>
                        </td>
                      </tr>
                    </tbody>
                  </v-table>
                  <p v-if="b.anzahl > b.stuecklisten.length" class="text-caption text-2 mt-2 mb-0">
                    … und {{ mehrzahl(b.anzahl - b.stuecklisten.length, 'weitere Stückliste', 'weitere Stücklisten') }} (Anzeige auf {{ f.grenze }} begrenzt).
                  </p>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>

          <div v-else>
            <p v-if="!f.modelle.length" class="text-body-2 text-2">Keine der Stücklisten gehört zu einem Root-Material dieses Bereichs.</p>
            <template v-else>
              <v-text-field v-if="f.modelle.length > 10" v-model="modellQ" placeholder="Modell suchen" prepend-inner-icon="mdi-magnify" clearable class="mb-2" aria-label="Modell suchen" />
              <v-table density="compact" class="tabelle">
                <thead><tr><th>Modell</th><th class="text-right">Stücklisten mit dem Wert</th></tr></thead>
                <tbody>
                  <tr v-for="m in modelle" :key="m.matnr">
                    <td>
                      <button type="button" class="link mono" title="Material öffnen" @click="oeffne(m.matnr)">{{ m.matnr }}</button>
                      <span class="text-2 zusatz">{{ m.kurztext }}</span>
                      <v-chip v-if="m.ausgeschlossen" size="x-small" variant="tonal" class="ml-2">vom Fachbereich ausgeschlossen</v-chip>
                    </td>
                    <td class="text-right mono">{{ m.stuecklisten }}</td>
                  </tr>
                </tbody>
              </v-table>
            </template>
          </div>
        </template>
      </template>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Schließen</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Fundstellen } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { mehrzahl } from '@/utils/texte'
import QuelltextAnzeige from '@/components/QuelltextAnzeige.vue'

const props = defineProps<{ daten: { merkmal: string; wert: string } }>()
const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const f = ref<Fundstellen | null>(null)
const laedt = ref(false)
const fehler = ref('')
const reiter = ref('beziehungen')
const offen = ref<string[]>([])
const modellQ = ref('')

const titel = computed(() => {
  const n = a.mName(props.daten.merkmal)
  return props.daten.wert === 'vorhanden' ? `„${n}“` : `${n} = ${props.daten.wert}`
})
const modelle = computed(() => {
  const q = (modellQ.value || '').trim().toUpperCase()
  const alle = f.value?.modelle || []
  return q ? alle.filter((m) => m.matnr.includes(q) || m.kurztext.toUpperCase().includes(q)) : alle
})

onMounted(async () => {
  laedt.value = true
  try {
    f.value = await a.ladeFundstellen(props.daten.merkmal, props.daten.wert)
    // wenige Beziehungswissen gleich aufgeklappt, sonst nur das häufigste
    offen.value = f.value.beziehungen.slice(0, f.value.beziehungen.length <= 3 ? 3 : 1).map((b) => b.knnum)
  } catch (e) {
    fehler.value = (e as Error).message
  } finally {
    laedt.value = false
  }
})

function oeffne(matnr: string) {
  emit('schliessen')
  a.oeffneMaterial(matnr)
}
</script>

<style scoped>
.zahlen { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.zahlen > div { border: 1px solid var(--linie); border-radius: 8px; padding: 8px 12px; display: flex; flex-direction: column; }
.zahlen strong { font-size: 20px; font-weight: 650; line-height: 1.2; }
.zahlen span { font-size: 12px; color: var(--text-2); }
.bw-kopf { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; width: 100%; padding-right: 8px; min-width: 0; }
.bw-text { flex-basis: 100%; min-width: 0; }
.knnam { font-size: 13px; word-break: break-all; }
.tabelle { font-size: 12.5px; border: 1px solid var(--linie); border-radius: 8px; }
.tabelle td { vertical-align: top; padding-top: 4px !important; padding-bottom: 4px !important; }
.link { border: 0; background: transparent; padding: 0; color: rgb(var(--v-theme-primary)); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.link:hover { text-decoration-thickness: 2px; }
.zusatz { margin-left: 6px; }
</style>
