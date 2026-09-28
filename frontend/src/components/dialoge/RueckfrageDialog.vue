<template>
  <v-dialog :model-value="Boolean(r)" max-width="460" @update:model-value="(v) => !v && r?.aufloesen(false)">
    <v-card v-if="r">
      <v-card-title class="pt-5 px-6">{{ r.titel }}</v-card-title>
      <v-card-text class="px-6 text-body-2" style="white-space: pre-line">{{ r.text }}</v-card-text>
      <v-card-actions class="px-6 pb-5">
        <v-spacer />
        <v-btn variant="text" @click="r.aufloesen(false)">{{ r.nein || 'Abbrechen' }}</v-btn>
        <v-btn :color="r.gefahr ? 'error' : 'primary'" @click="r.aufloesen(true)">{{ r.ja }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUi } from '@/stores/ui'

const ui = useUi()
const r = computed(() => ui.rueckfrage)
</script>
