<template>
  <v-card>
    <v-card-title class="pt-5 px-6">Kürzel „<span class="mono">{{ daten.alias }}</span>“ zuordnen</v-card-title>
    <v-card-text class="px-6">
      <p class="text-body-2 mb-2">Zu welchem Merkmal gehört dieses Kürzel in den Bedingungsnamen?</p>
      <p v-if="beispiele.length" class="text-body-2 text-2 mb-4">
        Kommt vor in: <template v-for="(b, i) in beispiele" :key="b">{{ i ? ', ' : '' }}<code>{{ b }}</code></template>
        – der Teil nach „{{ daten.alias }}“ ist der Wert.
      </p>
      <v-autocomplete v-model="auswahl" :items="eintraege" item-title="titel" item-value="wert" placeholder="Merkmal suchen, z. B. „Sitz“"
        autofocus auto-select-first clearable aria-label="Merkmal" no-data-text="Kein bekanntes Merkmal – unten neu eintragen" />
      <v-checkbox-btn v-model="neu" label="Anderes Merkmal (SAP-Namen eintippen)" density="compact" class="mt-2" />
      <v-text-field v-if="neu" v-model="neuName" placeholder="SAP-Name des Merkmals, z. B. SITZTIEFE" class="mt-1" aria-label="Neues Merkmal"
        hint="Wird beim Übernehmen angelegt." persistent-hint />
      <v-alert v-if="fehler" type="warning" variant="tonal" density="compact" class="mt-3">{{ fehler }}</v-alert>
      <p class="text-caption text-2 mt-4 mb-0">Die Zuordnung landet im Entwurf – der Baum zeigt sofort, was sich ändert.</p>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Abbrechen</v-btn>
      <v-btn color="primary" @click="ok">Zuordnen</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'

const props = defineProps<{ daten: { alias: string } }>()
const emit = defineEmits<{ schliessen: [] }>()
const a = useArbeit()
const ui = useUi()
const auswahl = ref<string | null>(a.entwurf.aliasse[props.daten.alias]?.merkmal || null)
const neu = ref(false)
const neuName = ref('')
const fehler = ref('')

const beispiele = computed<string[]>(() => a.meta?.kuerzel_beispiele?.[props.daten.alias] || [])
const eintraege = computed(() => {
  const technisch = new Set(Object.keys(a.basisRegeln).filter((k) => k.endsWith('|vorhanden')).map((k) => k.split('|')[0]))
  const alle = new Set<string>([...(a.meta?.merkmale || []), ...Object.keys(a.merkmale), ...Object.keys(a.basisRegeln).map((k) => k.split('|')[0])])
  return [...alle].filter((m) => !technisch.has(m) && !a.merkmale[m]?.systemregel)
    .map((m) => ({ wert: m, titel: a.mName(m) !== m ? `${a.mName(m)} (${m})` : m }))
    .sort((x, y) => x.titel.localeCompare(y.titel, 'de'))
})

function ok() {
  const m = (neu.value ? neuName.value : auswahl.value || '').trim().toUpperCase()
  if (!m) { fehler.value = 'Bitte ein Merkmal auswählen oder eintragen.'; return }
  a.setzeKuerzel(props.daten.alias, m, 'BASIS')
  emit('schliessen')
  ui.melde(`Kürzel ${props.daten.alias} → ${a.mName(m)} im Entwurf.`)
}
</script>
