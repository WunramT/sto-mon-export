<template>
  <div class="bewertung" role="group" :aria-label="`Bewertung für ${p.matnr || 'Position ' + p.posnr}`">
    <v-tooltip :text="gesperrt ? sperre : 'Richtig: der Status dieser Zeile passt'">
      <template #activator="{ props }">
        <span v-bind="props">
          <button type="button" class="bew ok" :class="{ an: u?.urteil === 'richtig' }" :disabled="gesperrt" :aria-pressed="u?.urteil === 'richtig'"
            data-test="bew-richtig" @click.stop="setze('richtig')">
            <v-icon icon="mdi-check" size="15" /> Richtig
          </button>
        </span>
      </template>
    </v-tooltip>
    <v-tooltip :text="gesperrt ? sperre : zweit[2]">
      <template #activator="{ props }">
        <span v-bind="props">
          <button type="button" class="bew nein" :class="{ an: u?.urteil === zweit[0] }" :disabled="gesperrt" :aria-pressed="u?.urteil === zweit[0]"
            data-test="bew-falsch" @click.stop="setze(zweit[0])">
            <v-icon :icon="imErg ? 'mdi-minus-circle-outline' : 'mdi-plus-circle-outline'" size="15" /> {{ zweit[1] }}
          </button>
        </span>
      </template>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { IM_ERGEBNIS } from '@/utils/texte'

const props = defineProps<{ p: any }>()
const a = useArbeit()
const sperre = 'Erst den Entwurf übernehmen oder verwerfen – bewertet wird der gespeicherte Regelstand.'
const u = computed(() => a.urteilVon(props.p.id))
const gesperrt = computed(() => !a.entwurfLeer)
const imErg = computed(() => IM_ERGEBNIS.has(props.p.status))
const zweit = computed(() => imErg.value
  ? ['gehoert_nicht_rein', 'Sollte raus', 'Falsch: gehört NICHT in die Basis-Stückliste']
  : ['fehlt', 'Sollte rein', 'Falsch: gehört in die Basis-Stückliste'])
function setze(urteil: string) { a.setzeUrteil(props.p.id, u.value?.urteil === urteil ? null : urteil) }
</script>

<style scoped>
.bewertung { display: flex; gap: 4px; justify-content: flex-end; }
.bew { display: inline-flex; align-items: center; gap: 3px; border: 1px solid var(--linie-2); background: #fff; border-radius: 6px; padding: 3px 8px; font-size: 12px; color: var(--text-2); cursor: pointer; white-space: nowrap; }
.bew:hover:not(:disabled) { background: var(--hover); color: var(--text-1); }
.bew:disabled { opacity: .45; cursor: not-allowed; }
.bew.ok.an { background: var(--s-basis); border-color: var(--s-basis); color: #fff; }
.bew.nein.an { background: #b3261e; border-color: #b3261e; color: #fff; }
</style>
