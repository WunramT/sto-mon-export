<template>
  <div class="quelltext-box">
    <pre v-if="text" class="quelltext mono" title="Quelltext des Beziehungswissens (SAP-Tabelle CUKN)">{{ text }}</pre>
    <div v-else-if="!prozedur" class="rueckfall">kein Quelltext in CUKN – aus dem Namen gelesen</div>
  </div>
</template>

<script setup lang="ts">
// Quelltext einer Bedingung (CUKN) neben ihrem Namen (KNNAM); ohne Text liest das Backend den Namen (Rückfall).
defineProps<{ text?: string | null; prozedur?: boolean }>()
</script>

<style scoped>
.quelltext { margin: 2px 0 4px; font-size: 11.5px; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text-2); font-weight: 400; }
.rueckfall { margin: 2px 0 4px; font-size: 11.5px; color: var(--text-3); font-style: italic; font-weight: 400; }
</style>
