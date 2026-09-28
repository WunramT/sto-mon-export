<template>
  <v-card>
    <v-card-title class="pt-5 px-6">So funktioniert die Basis-Stückliste</v-card-title>
    <v-card-text class="px-6 text-body-2">
      <p class="mb-4">Für jedes Merkmal (z. B. Sitzqualität) legt der Fachbereich fest, welche Werte zur Basis gehören und in welcher Rangfolge. Kommen auf einer Stückliste mehrere Basiswerte vor, gewinnt der mit dem kleinsten Rang.</p>
      <h3 class="abschnitt-titel">Status im Baum</h3>
      <div class="legende mb-4">
        <template v-for="st in STATUS_REIHENFOLGE" :key="st">
          <StatusPille :status="st" /><span>{{ STATUS[st].hilfe }}</span>
        </template>
      </div>
      <p class="text-2 mb-4">Regelwerte: „Basis“ = gehört zur Basis (Rang 1 gewinnt), „Nie Basis“ = nie, „Offen“ = noch keine Entscheidung. Werte, die in keiner Stückliste vorkommen, sind ausgegraut und brauchen keine Entscheidung.</p>
      <h3 class="abschnitt-titel">Ablauf</h3>
      <ol class="ablauf mb-4">
        <li>Material wählen, offene Fragen rechts klären – jede Regeländerung ist zunächst ein <strong>Entwurf</strong> nur für Sie.</li>
        <li>„Auswirkung auf alle Materialien“ zeigt, welche anderen Stücklisten sich mitändern.</li>
        <li>„Übernehmen“ speichert die Regeln für alle (mit Name und Begründung).</li>
        <li>Zeilen bewerten: „Richtig“, wenn der Status passt; „Sollte raus“ bzw. „Sollte rein“, wenn er falsch ist. Speichern.</li>
        <li>Positionen „Manuell prüfen“ (z. B. Klassenpositionen) entscheiden Sie selbst mit „Sollte rein“ oder „Sollte raus“ – oder klären vorher die Regelfrage.</li>
        <li>Bestätigen geht, sobald alle Zeilen gespeichert sind, alle regelentschiedenen Zeilen „Richtig“ und alle offenen manuell entschieden sind. Der SAP-Format-Export enthält die manuell hinzugenommenen und ergänzten Materialien.</li>
        <li>Ihr Entwurf und Ihre ungespeicherten Bewertungen bleiben auch nach dem Neuladen erhalten.</li>
      </ol>
      <h3 class="abschnitt-titel">Tastatur im Baum</h3>
      <p class="text-2 mb-0"><kbd>↑</kbd> <kbd>↓</kbd> Position wählen · <kbd>←</kbd> <kbd>→</kbd> zu-/aufklappen · <kbd>R</kbd> Richtig · <kbd>F</kbd> Sollte raus/rein · <kbd>E</kbd> offene Position „Sollte rein“</p>
    </v-card-text>
    <v-card-actions class="px-6 pb-5">
      <v-spacer />
      <v-btn color="primary" @click="$emit('schliessen')">Verstanden</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import StatusPille from '@/components/StatusPille.vue'
import { STATUS, STATUS_REIHENFOLGE } from '@/utils/texte'

defineEmits<{ schliessen: [] }>()
</script>

<style scoped>
.legende { display: grid; grid-template-columns: auto 1fr; gap: 8px 14px; align-items: center; }
.ablauf { padding-left: 18px; line-height: 1.6; }
kbd { font-family: inherit; font-size: 11px; border: 1px solid var(--linie-2); border-bottom-width: 2px; border-radius: 4px; padding: 0 5px; background: #fff; }
</style>
