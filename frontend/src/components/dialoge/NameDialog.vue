<template>
  <v-card>
    <v-card-title class="pt-5 px-6">Wie heißen Sie?</v-card-title>
    <v-card-text class="px-6">
      <p class="text-body-2 text-2 mb-4">Ihr Name wird bei Regeländerungen und Bewertungen gespeichert, damit nachvollziehbar ist, wer was entschieden hat. Ihr Entwurf wird unter diesem Namen auf dem Server gemerkt.</p>
      <v-text-field v-model="name" placeholder="Vorname Nachname" autofocus :error-messages="fehler" aria-label="Name" @keydown.enter="speichern" />
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn variant="text" @click="$emit('schliessen')">Abbrechen</v-btn>
      <v-btn color="primary" @click="speichern">Speichern</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '@/stores/auth'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'

const emit = defineEmits<{ schliessen: [] }>()
const auth = useAuth()
const a = useArbeit()
const ui = useUi()
const name = ref(auth.name)
const fehler = ref('')

async function speichern() {
  const n = name.value.trim()
  if (!n) { fehler.value = 'Bitte einen Namen eingeben.'; return }
  const wechsel = n !== auth.name
  if (wechsel && a.reviewStand.ungespeichert && !(await ui.frage({ titel: 'Name wechseln?', text: 'Ungespeicherte Bewertungen bleiben unter dem bisherigen Namen in diesem Browser erhalten.', ja: 'Wechseln' }))) return
  emit('schliessen')
  if (!wechsel) return
  a.entwurfGeaendert()  // eigenen Entwurf noch sichern
  auth.setzeName(n)
  // Entwurf, Bewertungen und Kontext gehören zum Namen – frisch laden
  setTimeout(() => window.location.reload(), 400)
}
</script>
