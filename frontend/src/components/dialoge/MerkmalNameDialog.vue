<template>
  <v-card>
    <v-card-title class="pt-5 px-6">Anzeigename für <span class="mono">{{ daten.merkmal }}</span></v-card-title>
    <v-card-text class="px-6">
      <p class="text-body-2 text-2 mb-4">So heißt das Merkmal in dieser Oberfläche – für alle. Der SAP-Name bleibt klein daneben sichtbar. Leer lassen = SAP-Name.</p>
      <v-text-field v-model="text" placeholder="z. B. Sitzqualität" autofocus aria-label="Anzeigename" @keydown.enter="speichern" />
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Abbrechen</v-btn>
      <v-btn color="primary" :loading="laedt" @click="speichern">Speichern</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'

const props = defineProps<{ daten: { merkmal: string } }>()
const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const ui = useUi()
const text = ref(a.mName(props.daten.merkmal) === props.daten.merkmal ? '' : a.mName(props.daten.merkmal))
const laedt = ref(false)

async function speichern() {
  laedt.value = true
  try { await a.setzeMerkmalName(props.daten.merkmal, text.value); emit('schliessen') } catch (e) { ui.melde((e as Error).message, true) } finally { laedt.value = false }
}
</script>
