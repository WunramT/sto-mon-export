<template>
  <v-dialog :model-value="Boolean(ui.dialog)" :max-width="breite" scrollable @update:model-value="(v) => !v && schliesse()">
    <component :is="komponente" v-if="ui.dialog && komponente" :daten="ui.dialog.daten" @schliessen="schliesse()" />
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUi } from '@/stores/ui'
import { useArbeit } from '@/stores/arbeit'
import NameDialog from './NameDialog.vue'
import KuerzelDialog from './KuerzelDialog.vue'
import ErgaenzenDialog from './ErgaenzenDialog.vue'
import UebernehmenDialog from './UebernehmenDialog.vue'
import HilfeDialog from './HilfeDialog.vue'
import MerkmalNameDialog from './MerkmalNameDialog.vue'
import DatenstandDialog from './DatenstandDialog.vue'

const ui = useUi()
const a = useArbeit()
// Klassenposition „rein“ ohne gewähltes Material (Abbrechen, Esc, daneben klicken) → „rein“ zurücknehmen
function schliesse() {
  const d = ui.dialog
  if (d?.art === 'ergaenzen' && d.daten?.klasseId && !d.daten.erledigt) {
    a.setzeUrteil(d.daten.klasseId, null)
    ui.melde('„Sollte rein“ zurückgenommen – ohne Material bleibt die Klassenposition offen.')
  }
  ui.schliesse()
}
const KOMPONENTEN: Record<string, any> = {
  name: NameDialog, kuerzel: KuerzelDialog, ergaenzen: ErgaenzenDialog, uebernehmen: UebernehmenDialog,
  hilfe: HilfeDialog, merkmalname: MerkmalNameDialog, datenstand: DatenstandDialog,
}
const BREITE: Record<string, number> = { hilfe: 680, datenstand: 720, uebernehmen: 600, kuerzel: 520, ergaenzen: 560 }
const komponente = computed(() => (ui.dialog ? KOMPONENTEN[ui.dialog.art] : null))
const breite = computed(() => (ui.dialog ? BREITE[ui.dialog.art] || 480 : 480))
</script>
