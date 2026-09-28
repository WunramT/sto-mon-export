<template>
  <span class="pille-rahmen">
    <span v-if="manuell" class="st" :class="manuell === 'rein' ? 'st-basis' : 'st-ausgeschlossen'" :title="`${STATUS[status]?.text}: manuell entschieden (${manuell === 'rein' ? 'kommt in die Basis' : 'kommt nicht in die Basis'})`">
      <v-icon icon="mdi-account-check-outline" size="13" />{{ manuell === 'rein' ? 'Manuell: rein' : 'Manuell: raus' }}
    </span>
    <span v-else class="st" :class="`st-${status}`" :title="STATUS[status]?.text"><span class="pkt" />
      <template v-if="kurz">{{ STATUS[status]?.kurz }}</template>
      <template v-else><span class="lang">{{ STATUS[status]?.text || status }}</span><span class="kurz">{{ STATUS[status]?.kurz || status }}</span></template>
    </span>
    <span v-if="vorher" class="vorher" :title="`Vor dem Entwurf: ${STATUS[vorher]?.text || vorher}`">vorher {{ STATUS[vorher]?.kurz || vorher }}</span>
  </span>
</template>

<script setup lang="ts">
import { STATUS } from '@/utils/texte'

defineProps<{ status: string; vorher?: string | null; kurz?: boolean; manuell?: 'rein' | 'raus' | null }>()
</script>

<style scoped>
.pille-rahmen { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.kurz { display: none; }
@media (max-width: 1440px) { .pille-rahmen .lang { display: none; } .pille-rahmen .kurz { display: inline; } }
.vorher { font-size: 11px; color: var(--entwurf); text-decoration: line-through; text-decoration-color: rgba(106, 63, 181, .45); padding-left: 8px; }
</style>
