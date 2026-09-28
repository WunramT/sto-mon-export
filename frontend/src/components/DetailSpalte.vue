<template>
  <aside ref="el" class="details-rahmen" aria-label="Details">
    <!-- Regeln: vollständige Liste offener Fragen -->
    <div v-if="a.ansicht === 'regeln'" class="details">
      <h2 class="titel">Offene Regelfragen</h2>
      <p class="unter">Diese Liste ist vollständig: die Zahl am Reiter „Regeln“ zählt genau diese Fragen.</p>
      <div v-if="!a.regelDaten" class="text-center py-6"><v-progress-circular indeterminate color="primary" size="28" /></div>
      <template v-else>
        <FragenListe v-if="a.regelDaten.fragen.length" titel="Zu entscheiden" :fragen="a.regelDaten.fragen" :zusatz="stl" @klick="springe" />
        <v-alert v-else type="success" variant="tonal" density="compact" class="mb-4">Alle Regelfragen sind entschieden.</v-alert>
        <FragenListe v-if="a.regelDaten.hinweise.length" titel="Nicht lesbare Bedingungen (nur in SAP lösbar)" :fragen="a.regelDaten.hinweise" :zusatz="stl" />
      </template>
    </div>

    <!-- Auswirkung: Lesehilfe -->
    <div v-else-if="a.ansicht === 'auswirkung'" class="details">
      <h2 class="titel">Auswirkung lesen</h2>
      <ul class="einfach">
        <li>Jede Zeile ist ein Material, dessen Basis-Stückliste sich durch Ihren Entwurf ändert.</li>
        <li>„Geänderte Positionen“: wie viele Positionen von welchem Status in welchen wechseln.</li>
        <li>„In der Basis-Stückliste“: Anzahl Positionen vorher → nachher.</li>
        <li>Klick auf eine Zeile öffnet das Material mit dem Entwurf.</li>
      </ul>
      <p class="unter">Nichts wird gespeichert, bevor Sie „Übernehmen“ wählen.</p>
    </div>

    <div v-else-if="!d || d.fehler" class="details"><p class="unter">Hier erscheinen Details zur gewählten Position.</p></div>

    <!-- Material ohne Auswahl: Was ist zu tun? -->
    <div v-else-if="!p" class="details">
      <h2 class="titel">Was ist zu tun?</h2>
      <p class="unter">Wählen Sie im Baum eine Position, um zu sehen, warum sie diesen Status hat.</p>
      <FragenListe v-if="d.fragen.length" titel="Offene Regelfragen in diesem Material" :fragen="d.fragen" :zusatz="pos" @klick="festlegen" />
      <v-alert v-else type="success" variant="tonal" density="compact" class="mb-4">Keine offenen Regelfragen in diesem Material.</v-alert>
      <FragenListe v-if="d.hinweise.length" titel="Nicht lesbare Bedingungen (nur in SAP lösbar)" :fragen="d.hinweise" :zusatz="pos" zeigbar @klick="zeige" />
      <p v-if="(a.meta?.offen || 0) > d.fragen.length" class="unter">
        Insgesamt {{ a.meta.offen }} offene Regelfragen – alle im Reiter
        <button type="button" class="link" @click="a.ansicht = 'regeln'">„Regeln“</button>.
      </p>
      <section class="abschnitt">
        <h3 class="abschnitt-titel">So geht's</h3>
        <ol class="einfach">
          <li>Offene Fragen klären: Basiswerte festlegen – der Baum rechnet sofort neu.</li>
          <li>Mit „Auswirkung auf alle Materialien“ prüfen, was der Entwurf sonst ändert.</li>
          <li>„Übernehmen“ speichert die Regeln für alle.</li>
          <li>Zeilen bewerten, speichern und das Material bestätigen.</li>
        </ol>
      </section>
    </div>

    <!-- Position -->
    <div v-else class="details">
      <div class="d-flex align-start justify-space-between ga-2">
        <div class="min-w-0">
          <h2 class="titel mono">{{ p.matnr || (p.postp === 'K' ? 'Klassenposition' : 'Position') }}</h2>
          <div class="kt">{{ p.kurztext }}</div>
          <div class="unter">Position {{ p.posnr }} · Ebene {{ p.ebene }}</div>
        </div>
        <v-btn icon="mdi-close" size="small" variant="text" aria-label="Auswahl aufheben" @click="a.auswahl = null" />
      </div>
      <div class="my-2"><StatusPille :status="p.status" :vorher="p.vorher" /></div>
      <div class="erklaerung">{{ p.erklaerung }}</div>

      <section v-if="p.fragen.length" class="abschnitt">
        <h3 class="abschnitt-titel">Offene Fragen</h3>
        <div v-for="f in p.fragen" :key="f.schluessel" class="frage">
          <span>{{ f.text }}</span>
          <v-btn v-if="f.typ === 'kuerzel'" size="x-small" variant="tonal" color="primary" @click="ui.oeffne('kuerzel', { alias: f.alias })">Zuordnen</v-btn>
          <v-btn v-else-if="f.merkmal" size="x-small" variant="tonal" color="primary" @click="fokus(f.merkmal)">Festlegen</v-btn>
        </div>
      </section>

      <section v-if="merkmaleHier.length" class="abschnitt">
        <h3 class="abschnitt-titel">Regeln für diese Position</h3>
        <p class="unter mb-2">Änderungen wirken sofort als Entwurf – der Baum zeigt die Folgen.</p>
        <template v-for="mn in merkmaleHier" :key="mn">
          <MerkmalKarte v-if="a.merkmale[mn]" :m="a.merkmale[mn]" :hier-werte="hierWerte(mn)" :gewaehlt="ebene ? ebene.gewaehlt[mn] ?? null : undefined"
            :hervor="a.fokusMerkmal === mn" :vorlaeufig="Boolean(ebene?.marker?.includes(`offen_neben_rang:${mn}`))" />
        </template>
      </section>

      <section class="abschnitt">
        <h3 class="abschnitt-titel">Bewertung</h3>
        <p v-if="a.bewertenGesperrt" class="unter">{{ a.bewertenGesperrt }}</p>
        <BewertungKnoepfe :p="p" class="justify-start mb-2 gross" />
        <v-textarea :model-value="urteil?.kommentar || ''" :placeholder="urteil?.urteil ? 'Kommentar (optional) – z. B. warum die Zeile falsch ist' : 'Erst bewerten, dann kommentieren'" rows="2" auto-grow
          :disabled="Boolean(a.bewertenGesperrt) || !urteil?.urteil" aria-label="Kommentar" @update:model-value="(v) => a.setzeKommentar(p.id, v)" />
        <v-btn v-if="p.hat_kinder" size="small" variant="outlined" class="mt-2" prepend-icon="mdi-plus" :disabled="Boolean(a.bewertenGesperrt)"
          @click="ui.oeffne('ergaenzen', { parentId: p.id })">Fehlendes Material unter dieser Baugruppe</v-btn>
      </section>

      <section class="abschnitt">
        <h3 class="abschnitt-titel">Bedingungen (SAP)</h3>
        <template v-if="p.bedingungen.length">
          <div v-for="(b, i) in p.bedingungen" :key="i" class="bedingung">
            <div class="roh mono">{{ b.name }}<span v-if="b.rolle === 'prozedur_ignoriert'" class="text-3"> · Prozedur, wird ignoriert</span></div>
            <div v-for="(x, j) in b.pruefungen" :key="j" class="pruefung">
              <span class="ergebnis" :class="`e-${x.ergebnis}`">{{ x.ergebnis === 'passt' ? 'passt' : x.ergebnis === 'passt_nicht' ? 'passt nicht' : 'offen' }}</span>
              <span>{{ pruefText(x) }}</span>
            </div>
            <div v-if="b.fehler" class="pruefung"><span class="ergebnis e-manuell">unlesbar</span>{{ b.fehler }}</div>
          </div>
        </template>
        <p v-else class="unter">Keine Bedingung – die Position ist immer enthalten.</p>
        <p v-if="p.prozeduren.length" class="unter">Ignorierte Prozeduren: {{ p.prozeduren.join(', ') }}</p>
      </section>

      <section class="abschnitt">
        <h3 class="abschnitt-titel">Daten</h3>
        <dl class="kv">
          <dt>Menge je Baugruppe</dt><dd class="mono">{{ fmtMenge(p.menge, p.meins) }}</dd>
          <dt>Menge gesamt</dt>
          <dd><span class="mono">{{ fmtMenge(p.menge_kum, p.meins) }}</span>
            <small>{{ p.menge && p.menge_kum !== p.menge ? `= ${fmtZahl(p.menge)} × ${fmtZahl(p.menge_kum / p.menge)} (Mengen der Baugruppen darüber), bezogen auf 1 Stück ${d.matnr}` : `bezogen auf 1 Stück ${d.matnr}` }}</small></dd>
          <dt>Stückliste</dt><dd class="mono">{{ p.stlnr }}</dd>
          <dt>Positionstyp</dt><dd>{{ POSTP[p.postp] ? `${POSTP[p.postp]} (${p.postp})` : p.postp || '–' }}</dd>
        </dl>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import FragenListe from '@/components/FragenListe.vue'
import MerkmalKarte from '@/components/MerkmalKarte.vue'
import StatusPille from '@/components/StatusPille.vue'
import BewertungKnoepfe from '@/components/BewertungKnoepfe.vue'
import { POSTP, fmtMenge, fmtZahl, mehrzahl } from '@/utils/texte'

const a = useArbeit()
const ui = useUi()
const el = ref<HTMLElement | null>(null)
const d = computed(() => a.daten as any)
const p = computed(() => d.value?.positionen?.find((x: any) => x.id === a.auswahl) || null)
const ebene = computed(() => (p.value ? d.value.ebenen[p.value.stlnr] : null))
const urteil = computed(() => (p.value ? a.urteilVon(p.value.id) : null))
const merkmaleHier = computed<string[]>(() => (p.value ? [...new Set<string>(p.value.bedingungen.flatMap((b: any) => b.pruefungen.map((x: any) => x.merkmal)))] : []))
const hierWerte = (mn: string) => new Set<string>((ebene.value?.kandidaten?.[mn] || []).map((k: any) => k.wert))

const stl = (f: any) => `in ${mehrzahl(f.stuecklisten, 'Stückliste', 'Stücklisten')}`
const pos = (f: any) => `betrifft ${mehrzahl(f.positionen, 'Position', 'Positionen')} in diesem Material`

function pruefText(x: any) {
  const n = a.mName(x.merkmal)
  if (x.wert === 'vorhanden') return n
  if (x.wert.startsWith('≠')) return `${n} nicht ${x.wert.slice(1)}`
  return `${n} = ${x.wert}`
}

function fokus(merkmal: string) {
  a.fokusMerkmal = merkmal
  nextTick(() => el.value?.querySelector(`[data-merkmal="${CSS.escape(merkmal)}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }))
}

function zeige(f: any) { a.zeigePosition(f.beispiel, f.merkmal || null) }
function festlegen(f: any) {
  if (f.typ === 'unlesbar' || !f.merkmal) { zeige(f); return }
  // im Material bleiben: Position mit der Frage wählen und die Regel-Karte hervorheben
  a.zeigePosition(f.beispiel, f.merkmal)
  nextTick(() => fokus(f.merkmal))
}
function springe(f: any) {
  if (!f.merkmal) return
  a.regelnQ = ''
  a.fokusMerkmal = f.merkmal
  nextTick(() => document.querySelector(`.regel-liste [data-merkmal="${CSS.escape(f.merkmal)}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' }))
}

watch(() => a.auswahl, () => { if (!a.fokusMerkmal) el.value?.scrollTo({ top: 0 }) })
watch(() => a.fokusMerkmal, (m) => { if (m && p.value) nextTick(() => fokus(m)) })
</script>

<style scoped>
.details-rahmen { overflow-y: auto; }
.details { padding: 16px 18px 28px; }
.titel { font-size: 17px; font-weight: 700; margin: 0; letter-spacing: -0.01em; }
.kt { font-size: 13px; color: var(--text-2); }
.unter { font-size: 12.5px; color: var(--text-2); margin: 2px 0 8px; }
.erklaerung { font-size: 13.5px; line-height: 1.5; padding: 10px 12px; border-radius: 8px; background: #fff; border: 1px solid var(--linie); margin-bottom: 16px; }
.abschnitt { margin-bottom: 18px; }
.frage { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; padding: 8px 10px; border-radius: 8px; background: var(--s-manuell-bg); color: #6b4200; font-size: 13px; margin-bottom: 6px; }
.bedingung { padding: 8px 10px; border: 1px solid var(--linie); border-radius: 8px; background: #fff; margin-bottom: 6px; }
.roh { font-size: 12px; font-weight: 600; margin-bottom: 4px; word-break: break-all; }
.pruefung { display: flex; gap: 8px; align-items: center; font-size: 12.5px; padding: 2px 0; }
.ergebnis { font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; flex: none; }
.e-passt { background: var(--s-basis-bg); color: var(--s-basis); }
.e-passt_nicht { background: var(--s-aus-bg); color: var(--s-aus); }
.e-manuell { background: var(--s-manuell-bg); color: var(--s-manuell); }
.kv { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 6px 10px; font-size: 13px; margin: 0; }
.kv dt { color: var(--text-2); }
.kv dd { margin: 0; }
.kv small { display: block; color: var(--text-3); font-size: 11.5px; }
.einfach { padding-left: 18px; font-size: 13px; color: var(--text-2); line-height: 1.55; }
.min-w-0 { min-width: 0; }
.link { border: 0; background: none; padding: 0; color: var(--auswahl-rand); font-weight: 600; cursor: pointer; font-size: inherit; }
.link:hover { text-decoration: underline; }
.gross :deep(.bew) { width: auto; padding: 4px 10px; }
.gross :deep(.bew .txt) { display: inline; }
</style>
