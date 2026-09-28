<template>
  <v-app>
    <router-view />
    <v-snackbar
      v-model="ui.meldungOffen"
      :timeout="ui.meldung?.fehler || ui.meldung?.aktion ? 7000 : 3500"
      :color="ui.meldung?.fehler ? 'error' : 'secondary'"
      location="bottom center"
      :key="ui.meldung?.id"
    >
      <span role="status">{{ ui.meldung?.text }}</span>
      <template #actions>
        <v-btn v-if="ui.meldung?.aktion" variant="text" color="white" @click="aktion">{{ ui.meldung.aktion.text }}</v-btn>
        <v-btn icon="mdi-close" variant="text" size="small" aria-label="Meldung schließen" @click="ui.meldungOffen = false" />
      </template>
    </v-snackbar>
    <RueckfrageDialog />
  </v-app>
</template>

<script setup lang="ts">
import { useUi } from '@/stores/ui'
import RueckfrageDialog from '@/components/dialoge/RueckfrageDialog.vue'

const ui = useUi()
function aktion() {
  const a = ui.meldung?.aktion
  ui.meldungOffen = false
  a?.tun()
}
</script>
