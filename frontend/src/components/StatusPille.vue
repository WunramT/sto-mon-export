<template>
  <span class="pille-rahmen">
    <span class="st" :class="`st-${status}`"><span class="pkt" />{{ kurz ? STATUS[status]?.kurz : STATUS[status]?.text || status }}</span>
    <span v-if="vorher" class="vorher" :title="`Vor dem Entwurf: ${STATUS[vorher]?.text || vorher}`">vorher {{ STATUS[vorher]?.kurz || vorher }}</span>
  </span>
</template>

<script setup lang="ts">
import { STATUS } from '@/utils/texte'

defineProps<{ status: string; vorher?: string | null; kurz?: boolean }>()
</script>

<style scoped>
.pille-rahmen { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; }
.vorher { font-size: 11px; color: var(--entwurf); text-decoration: line-through; text-decoration-color: rgba(106, 63, 181, .45); padding-left: 8px; }
</style>
