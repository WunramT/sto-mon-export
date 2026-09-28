<template>
  <div class="zeile" :class="{ gewaehlt: a.auswahl === p.id, geaendert: p.vorher, raus: RAUS.has(p.status), kontext }"
    role="treeitem" :aria-level="p.ebene" :aria-selected="a.auswahl === p.id" :aria-expanded="p.hat_kinder ? !a.zu.has(p.id) : undefined"
    :aria-label="`${p.posnr} ${p.matnr || (p.postp === 'K' ? 'Klassenposition' : 'Textposition')} ${p.kurztext || ''}, ${STATUS[p.status]?.text || p.status}`"
    :data-id="p.id" @click="waehle">
    <div class="name">
      <span class="einzug" :style="{ width: `${(p.ebene - 1) * 18}px` }" />
      <button v-if="p.hat_kinder" type="button" class="pfeil" tabindex="-1" aria-hidden="true" @click.stop="a.klappe(p.id)">
        <v-icon :icon="a.zu.has(p.id) ? 'mdi-chevron-right' : 'mdi-chevron-down'" size="18" />
      </button>
      <span v-else class="pfeil leer" />
      <span class="pkt" :class="`pkt-${p.status}`" />
      <div class="name-text">
        <div class="zeile1">
          <span class="pos mono">{{ p.posnr }}</span>
          <span class="mat mono">{{ p.matnr || (p.postp === 'K' ? 'Klassenposition' : 'Textposition') }}</span>
          <v-icon v-if="p.fragen?.length" icon="mdi-help-circle" size="14" color="warning" class="ml-1" :title="`${p.fragen.length} offene Frage(n)`" />
          <span v-if="urteil?.kommentar" class="kommentar-icon" :title="urteil.kommentar"><v-icon icon="mdi-comment-text-outline" size="13" /></span>
        </div>
        <div class="kt">{{ p.kurztext || (!p.matnr && p.postp === 'K' ? 'Material wird manuell gewählt' : '') }}</div>
      </div>
    </div>
    <div class="menge mono">{{ fmtMenge(p.menge_kum, p.meins) }}</div>
    <div><StatusPille :status="p.status" :vorher="p.vorher" /></div>
    <BewertungKnoepfe :p="p" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import StatusPille from '@/components/StatusPille.vue'
import BewertungKnoepfe from '@/components/BewertungKnoepfe.vue'
import { RAUS, STATUS, fmtMenge } from '@/utils/texte'

const props = defineProps<{ p: any; kontext?: boolean }>()
const a = useArbeit()
const urteil = computed(() => a.urteilVon(props.p.id))

function waehle() {
  a.auswahl = props.p.id
  a.fokusMerkmal = null
}
</script>

<style scoped>
.zeile { height: 50px; border-bottom: 1px solid var(--linie); cursor: pointer; border-left: 3px solid transparent; padding-left: 15px !important; }
.zeile:hover { background: var(--hover); }
.zeile.gewaehlt { background: var(--auswahl); border-left-color: var(--auswahl-rand); }
.zeile.geaendert { background: #faf7ff; }
.zeile.geaendert.gewaehlt { background: var(--auswahl); }
.zeile.raus .mat, .zeile.raus .kt { color: var(--text-3); }
.zeile.kontext { opacity: .55; }
.name { display: flex; align-items: center; min-width: 0; gap: 4px; }
.einzug { flex: none; }
.pfeil { width: 22px; height: 22px; flex: none; display: grid; place-items: center; border: 0; background: transparent; border-radius: 4px; cursor: pointer; color: var(--text-2); }
.pfeil:hover { background: rgba(0, 0, 0, .06); }
.pfeil.leer { cursor: default; }
.pkt { width: 8px; height: 8px; border-radius: 50%; flex: none; margin: 0 4px 0 2px; }
.name-text { min-width: 0; display: flex; flex-direction: column; }
.zeile1 { display: flex; align-items: center; gap: 8px; }
.pos { font-size: 11.5px; color: var(--text-3); min-width: 28px; }
.mat { font-weight: 600; font-size: 13px; }
.kt { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.menge { text-align: right; font-size: 13px; }
.kommentar-icon { color: var(--text-3); }
</style>
