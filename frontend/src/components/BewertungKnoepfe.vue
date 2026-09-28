<template>
  <div class="bewertung" role="group" :aria-label="`Bewertung für ${p.matnr || 'Position ' + p.posnr}`">
    <v-tooltip v-for="k in knoepfe" :key="k.urteil" :text="sperre || k.titel">
      <template #activator="{ props }">
        <span v-bind="props">
          <button type="button" class="bew" :class="[k.art, { an: u?.urteil === k.urteil }]" :disabled="Boolean(sperre)"
            :aria-pressed="u?.urteil === k.urteil" :aria-label="k.text" :data-test="`bew-${k.test}`" @click.stop="setze(k.urteil)">
            <v-icon :icon="k.icon" size="15" /><span class="txt">{{ k.text }}</span>
          </button>
        </span>
      </template>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { IM_ERGEBNIS, OFFEN_STATUS } from '@/utils/texte'

const props = defineProps<{ p: any }>()
const a = useArbeit()
const u = computed(() => a.urteilVon(props.p.id))
const sperre = computed(() => a.bewertenGesperrt)

const RICHTIG = { urteil: 'richtig', text: 'Richtig', titel: 'Richtig: der Status dieser Zeile passt', icon: 'mdi-check', art: 'ok', test: 'richtig' }
const RAUS = { urteil: 'gehoert_nicht_rein', text: 'Sollte raus', titel: 'Falsch: gehört NICHT in die Basis-Stückliste', icon: 'mdi-minus-circle-outline', art: 'nein', test: 'falsch' }
const REIN = { urteil: 'fehlt', text: 'Sollte rein', titel: 'Falsch: gehört in die Basis-Stückliste', icon: 'mdi-plus-circle-outline', art: 'nein', test: 'falsch' }
// „Manuell prüfen“ ist nie einfach richtig: hier entscheidet der Fachbereich rein oder raus
const knoepfe = computed(() => OFFEN_STATUS.has(props.p.status)
  ? [{ ...REIN, art: 'rein', test: 'rein', titel: 'Gehört in die Basis-Stückliste' }, { ...RAUS, test: 'falsch', titel: 'Gehört nicht in die Basis-Stückliste' }]
  : [RICHTIG, IM_ERGEBNIS.has(props.p.status) ? RAUS : REIN])
function setze(urteil: string) { a.setzeUrteil(props.p.id, u.value?.urteil === urteil ? null : urteil) }
</script>

<style scoped>
.bewertung { display: flex; gap: 4px; justify-content: flex-end; }
.bew { display: inline-flex; align-items: center; justify-content: center; gap: 3px; border: 1px solid var(--linie-2); background: #fff; border-radius: 6px; padding: 3px 6px; font-size: 12px; color: var(--text-2); cursor: pointer; white-space: nowrap; width: 88px; }
.bew:hover:not(:disabled) { background: var(--hover); color: var(--text-1); }
.bew:disabled { opacity: .45; cursor: not-allowed; }
.bew.ok.an { background: var(--s-basis); border-color: var(--s-basis); color: #fff; }
.bew.rein.an { background: #2f6db3; border-color: #2f6db3; color: #fff; }
.bew.nein.an { background: #b3261e; border-color: #b3261e; color: #fff; }
@media (max-width: 1440px) { .bew { width: 34px; padding: 3px 0; } .bew .txt { display: none; } }
</style>
