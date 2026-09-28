<template>
  <div v-if="!a.entwurfLeer" class="entwurf-leiste" role="region" aria-label="Regel-Entwurf">
    <div class="info">
      <v-icon icon="mdi-pencil-ruler" size="18" />
      <strong>Entwurf</strong>
      <span>{{ mehrzahl(a.entwurfAnzahl, 'Änderung', 'Änderungen') }}</span>
      <span class="hinweis">nur für Sie sichtbar, bis Sie übernehmen</span>
    </div>
    <div class="chips">
      <v-chip v-for="e in a.entwurfListe" :key="e.alias || `${e.merkmal}|${e.wert}`" size="small" variant="outlined" color="deep-purple" class="chip"
        closable close-label="Diese Änderung zurücknehmen" @click:close="a.nimmZurueck(e)">
        {{ a.entwurfEintragText(e) }}
      </v-chip>
    </div>
    <div class="knoepfe">
      <v-btn size="small" variant="outlined" color="deep-purple" prepend-icon="mdi-compare-horizontal" @click="a.ansicht = 'auswirkung'">Auswirkung auf alle Materialien</v-btn>
      <v-btn size="small" variant="text" @click="verwerfen">Verwerfen</v-btn>
      <v-btn size="small" color="deep-purple" prepend-icon="mdi-check" data-test="uebernehmen-knopf" @click="ui.oeffne('uebernehmen')">Übernehmen …</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import { mehrzahl } from '@/utils/texte'

const a = useArbeit()
const ui = useUi()

async function verwerfen() {
  const ok = await ui.frage({ titel: 'Entwurf verwerfen?', text: `${mehrzahl(a.entwurfAnzahl, 'Änderung geht', 'Änderungen gehen')} verloren. Der übernommene Stand bleibt unverändert.`, ja: 'Entwurf verwerfen', gefahr: true })
  if (ok) a.verwerfen()
}
</script>

<style scoped>
.entwurf-leiste { flex: none; display: flex; align-items: center; gap: 14px; padding: 9px 16px; background: var(--entwurf-bg); border-bottom: 1px solid #d9cdf1; color: #3d2470; }
.info { display: flex; align-items: center; gap: 8px; font-size: 13px; white-space: nowrap; }
.hinweis { color: #6f5a99; font-size: 12px; }
.chips { flex: 1; min-width: 0; display: flex; gap: 6px; overflow-x: auto; padding: 2px 0; }
.chip { flex: none; background: #fff; }
.knoepfe { display: flex; gap: 6px; flex: none; }
@media (max-width: 1300px) { .hinweis { display: none; } }
</style>
