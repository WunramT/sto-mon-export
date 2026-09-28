<template>
  <section class="abschnitt">
    <h3 class="abschnitt-titel">{{ titel }} ({{ fragen.length }})</h3>
    <div v-for="f in fragen" :key="f.schluessel" class="frage" :class="{ unlesbar: f.typ === 'unlesbar' }">
      <v-icon :icon="f.typ === 'unlesbar' ? 'mdi-file-alert-outline' : f.typ === 'kuerzel' ? 'mdi-tag-outline' : 'mdi-help-circle-outline'" size="16" class="icon" />
      <div class="text">
        {{ f.text }}
        <small>{{ zusatz(f) }}</small>
      </div>
      <v-btn v-if="f.typ === 'kuerzel'" size="x-small" variant="tonal" color="primary" @click="ui.oeffne('kuerzel', { alias: f.alias })">Zuordnen</v-btn>
      <v-btn v-else-if="f.typ !== 'unlesbar' || zeigbar" size="x-small" variant="tonal" color="primary" @click="$emit('klick', f)">{{ f.typ === 'unlesbar' ? 'Zeigen' : 'Festlegen' }}</v-btn>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useUi } from '@/stores/ui'

defineProps<{ titel: string; fragen: any[]; zusatz: (f: any) => string; zeigbar?: boolean }>()
defineEmits<{ klick: [f: any] }>()
const ui = useUi()
</script>

<style scoped>
.abschnitt { margin-bottom: 18px; }
.frage { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; gap: 8px; align-items: start; padding: 9px 10px; border: 1px solid var(--linie); border-radius: 8px; background: #fff; margin-bottom: 6px; font-size: 13px; }
.frage.unlesbar { background: #fafafa; }
.icon { color: var(--s-manuell); margin-top: 1px; }
.unlesbar .icon { color: var(--text-3); }
.text small { display: block; color: var(--text-3); font-size: 11.5px; margin-top: 2px; }
</style>
