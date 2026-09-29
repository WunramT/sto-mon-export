<template>
  <div class="stueckliste">
    <div v-if="!a.daten" class="leer-hinweis">
      <template v-if="a.laedt">
        <v-progress-circular indeterminate color="primary" />
        <p v-if="langsam" class="text-body-2 mt-4">Der Server antwortet gerade langsam … Die Anfrage läuft weiter.</p>
      </template>
      <span v-else>Links ein Material wählen.</span>
    </div>

    <div v-else-if="a.daten.fehler" class="leer-hinweis">
      <v-icon icon="mdi-alert-circle-outline" size="36" color="warning" class="mb-2" />
      <div class="text-h6 mb-1">{{ a.daten.matnr }}</div>
      <p class="text-body-2">{{ a.daten.fehler }}</p>
    </div>

    <template v-else>
      <v-progress-linear :active="a.laedt" indeterminate color="primary" height="2" absolute />
      <header class="kopf">
        <v-alert v-if="a.laedt && langsam" type="info" variant="tonal" density="compact" class="mb-2 hinweis-mehrzeilig" icon="mdi-timer-sand">Der Server antwortet gerade langsam – die Berechnung läuft weiter …</v-alert>
        <div class="titelzeile">
          <div class="min-w-0">
            <h1 class="mat-titel"><span class="mono">{{ d.matnr }}</span> <span class="kt">{{ d.kurztext }}</span></h1>
            <div v-if="d.review?.bestaetigt" class="bestaetigt">
              <v-icon icon="mdi-check-decagram" size="16" color="success" />
              Bestätigt von {{ d.review.bestaetigt.von }} am {{ fmtDatum(d.review.bestaetigt.datum) }}
              <v-btn size="x-small" variant="text" class="ml-1" data-test="aufheben-knopf" @click="aufheben">Bestätigung aufheben</v-btn>
            </div>
            <div v-else-if="d.review?.stand" class="text-caption text-2">Zuletzt bewertet von {{ d.review.von }} · {{ fmtZeit(d.review.stand) }}</div>
          </div>
          <v-tooltip text="Basis-Stückliste als CSV im SAP-Format: übernommene Regeln + gespeicherte manuelle Entscheidungen und Ergänzungen (ohne Entwurf und ungespeicherte Bewertungen)">
            <template #activator="{ props }">
              <v-btn v-bind="props" variant="outlined" size="small" prepend-icon="mdi-download" :loading="exportLaedt" data-test="export-knopf" @click="exportiere">
                SAP-Format
              </v-btn>
            </template>
          </v-tooltip>
        </div>

        <div class="kennzahlen">
          <button type="button" class="kennzahl k-basis" :class="{ aktiv: a.filter === 'ergebnis' }" @click="umschalten('ergebnis')">
            <span class="wert mono">{{ k.basis }}<small v-if="k.ergaenzt"> + {{ k.ergaenzt }}</small></span>
            <span class="name"><span class="lang">in der Basis-Stückliste</span><span class="kurz">in Basis</span></span>
          </button>
          <button type="button" class="kennzahl k-offen" :class="{ aktiv: a.filter === 'offen' }" @click="umschalten('offen')">
            <span class="wert mono">{{ k.offen }}</span>
            <span class="name"><span class="lang">offen – manuell prüfen</span><span class="kurz">offen</span></span>
          </button>
          <button type="button" class="kennzahl k-aus" :class="{ aktiv: a.filter === 'raus' }" @click="umschalten('raus')">
            <span class="wert mono">{{ k.aus }}</span>
            <span class="name"><span class="lang">nicht in der Basis</span><span class="kurz">nicht Basis</span></span>
          </button>
          <button v-if="!a.entwurfLeer" type="button" class="kennzahl k-entwurf" :class="{ aktiv: a.filter === 'geaendert' }" @click="umschalten('geaendert')">
            <span class="wert mono">{{ d.geaendert }}</span>
            <span class="name"><span class="lang">durch Entwurf geändert</span><span class="kurz">geändert</span></span>
          </button>
        </div>

        <div class="werkzeuge">
          <v-btn-toggle v-model="a.filter" mandatory density="compact" variant="outlined" divided color="primary" class="segment" aria-label="Ansicht filtern">
            <v-btn value="alle" size="small">Alle</v-btn>
            <v-btn value="offen" size="small">Offene</v-btn>
            <v-btn value="ergebnis" size="small">Basis-Ergebnis</v-btn>
            <v-btn value="raus" size="small">Nicht Basis</v-btn>
            <v-btn value="unbewertet" size="small">Unbewertet</v-btn>
            <v-btn v-if="!a.entwurfLeer" value="geaendert" size="small">Geändert</v-btn>
          </v-btn-toggle>
          <v-text-field v-model="a.baumQ" placeholder="Im Baum suchen" prepend-inner-icon="mdi-magnify" clearable class="baum-suche" aria-label="Im Baum suchen" />
          <div class="klapp">
            <v-tooltip text="Alle Baugruppen aufklappen"><template #activator="{ props }"><v-btn v-bind="props" size="small" variant="text" icon="mdi-unfold-more-horizontal" aria-label="Alle aufklappen" @click="a.alleAuf()" /></template></v-tooltip>
            <v-tooltip text="Alle Baugruppen zuklappen"><template #activator="{ props }"><v-btn v-bind="props" size="small" variant="text" icon="mdi-unfold-less-horizontal" aria-label="Alle zuklappen" @click="a.alleZu()" /></template></v-tooltip>
          </div>
        </div>

        <div class="review-leiste">
          <div class="fortschritt">
            <div class="fz">
              <strong>Bewertet: {{ rs.bewertet }} von {{ rs.alle }}</strong>
              <span v-if="rs.ungespeichert" class="ungespeichert"> · {{ rs.ungespeichert }} ungespeichert</span>
              <span v-if="rs.ergaenzt" class="text-2"> · {{ rs.ergaenzt }} ergänzt</span>
            </div>
            <v-progress-linear :model-value="rs.alle ? (100 * rs.bewertet) / rs.alle : 0" color="success" bg-color="#dfe3e7" height="5" rounded />
          </div>
          <div class="knoepfe">
            <v-btn size="small" variant="outlined" :disabled="Boolean(a.bewertenGesperrt)" prepend-icon="mdi-check-all" class="sek" aria-label="Angezeigte als Richtig" title="Alle angezeigten Zeilen ohne Urteil als „Richtig“ markieren" @click="a.alleSichtbarenRichtig()"><span class="btxt">Angezeigte als Richtig</span><span class="btxt-kurz">Alle ✓</span></v-btn>
            <v-btn size="small" variant="outlined" :disabled="Boolean(a.bewertenGesperrt)" prepend-icon="mdi-plus" aria-label="Material ergänzen" title="Fehlendes Material ergänzen" @click="ui.oeffne('ergaenzen', { parentId: d.matnr })">Ergänzen</v-btn>
            <v-btn v-if="rs.ungespeichert" size="small" variant="text" @click="verwerfeBewertung">Verwerfen</v-btn>
            <v-btn size="small" :color="rs.ungespeichert ? 'primary' : undefined" :variant="rs.ungespeichert ? 'flat' : 'outlined'"
              :disabled="!rs.ungespeichert || Boolean(a.bewertenGesperrt)" :loading="speichert" prepend-icon="mdi-content-save-outline" data-test="speichern-knopf" @click="speichere">
              {{ rs.ungespeichert ? `Speichern (${rs.ungespeichert})` : 'Gespeichert' }}
            </v-btn>
            <v-chip v-if="d.review?.bestaetigt && !rs.ungespeichert" color="success" variant="flat" size="small" prepend-icon="mdi-check-decagram">Bestätigt</v-chip>
            <v-tooltip v-else :text="a.bestaetigbar ? 'Material als vollständig geprüft markieren' : 'Möglich, sobald alle Zeilen gespeichert mit „Richtig“ bewertet und keine Positionen mehr offen sind'">
              <template #activator="{ props }">
                <span v-bind="props"><v-btn size="small" :color="a.bestaetigbar ? 'success' : undefined" :variant="a.bestaetigbar ? 'flat' : 'tonal'" :disabled="!a.bestaetigbar"
                  prepend-icon="mdi-check-decagram-outline" data-test="bestaetigen-knopf" @click="bestaetige">Bestätigen</v-btn></span>
              </template>
            </v-tooltip>
          </div>
        </div>

        <v-alert v-if="d.review?.bestaetigt?.veraltet" type="warning" variant="tonal" density="compact" class="mt-2 hinweis" icon="mdi-alert-decagram-outline">
          <div class="d-flex align-center ga-3">
            <span class="flex-grow-1">Bestätigt, aber eine Regeländerung hat seitdem verändert, was exportiert wird – die Bestätigung passt nicht mehr zum Export. Bitte aufheben und neu bewerten.</span>
            <v-btn size="x-small" variant="outlined" @click="aufheben">Aufheben</v-btn>
          </div>
        </v-alert>
        <v-alert v-else-if="d.review?.bestaetigt" type="success" variant="tonal" density="compact" class="mt-2 hinweis" icon="mdi-lock-outline">
          Bestätigt und gesperrt – das Material dient als Referenz. Zum Ändern der Bewertung erst die Bestätigung aufheben.
        </v-alert>
        <v-alert v-if="a.sperrGrund && a.entwurfLeer" type="info" variant="tonal" density="compact" class="mt-2 hinweis">
          <div class="d-flex align-center ga-3">
            <span class="flex-grow-1">Bestätigen noch nicht möglich: {{ a.sperrGrund.text }}</span>
            <v-btn v-if="a.sperrGrund.ziel" size="x-small" variant="outlined" @click="zeige(a.sperrGrund.ziel)">Zeigen</v-btn>
          </div>
        </v-alert>
        <v-alert v-if="!a.entwurfLeer" type="info" variant="tonal" color="deep-purple" density="compact" class="mt-2 hinweis" icon="mdi-eye-outline">
          Sie sehen die Vorschau Ihres Entwurfs. Bewerten ist erst nach „Übernehmen“ oder „Verwerfen“ möglich.
        </v-alert>
        <v-alert v-if="d.review?.veraltet && !d.review?.bestaetigt" type="warning" variant="tonal" density="compact" class="mt-2 hinweis">
          Seit der letzten Bewertung haben sich Regeln geändert: {{ mehrzahl(d.review.veraltet, 'Position hat', 'Positionen haben') }} jetzt einen anderen Status. Bitte diese Zeilen neu bewerten.
        </v-alert>
        <v-alert v-if="d.warnungen?.length" type="info" variant="tonal" density="compact" class="mt-2 hinweis">{{ d.warnungen.join(' · ') }}</v-alert>
      </header>

      <div class="baum-kopf" role="presentation">
        <div>Position · Material</div><div class="r" title="Menge gesamt, bezogen auf 1 Stück des Materials (der SAP-Export enthält die Menge je Baugruppe)">Menge ges.</div><div>Status</div><div class="r">Bewertung</div>
      </div>
      <div ref="baumEl" class="baum" role="tree" :aria-label="`Stückliste ${d.matnr}`" tabindex="0" @keydown="taste">
        <v-virtual-scroll v-if="zeilen.length" ref="scroller" :items="zeilen" item-height="50" height="100%">
          <template #default="{ item }">
            <BaumZeile v-if="item.art === 'pos'" :p="item.p" :kontext="item.kontext" />
            <div v-else-if="item.art === 'titel'" class="gruppen-titel">Als fehlend ergänzt</div>
            <div v-else class="zeile ergaenzt">
              <div class="name">
                <span class="pkt pkt-ergaenzt" />
                <div class="name-text">
                  <div class="zeile1"><span class="mat mono">{{ item.e.matnr }}</span> <span class="kt">{{ item.e.kurztext }}</span></div>
                  <div class="kt">{{ item.e.parent_matnr ? `unter ${item.e.parent_matnr}` : 'für Klassenposition' }}<template v-if="item.e.kommentar"> – {{ item.e.kommentar }}</template></div>
                </div>
              </div>
              <div class="menge mono" title="Menge je Baugruppe (wie eingegeben)">{{ fmtMenge(item.e.menge, item.e.meins || 'ST') }}<small class="text-3"> je Bgr.</small></div>
              <div><span class="st st-ergaenzt"><span class="pkt" />{{ item.e.lokal ? 'ergänzt · ungespeichert' : 'ergänzt' }}</span></div>
              <div class="r"><v-btn size="x-small" variant="outlined" :disabled="Boolean(a.bewertenGesperrt)" @click="a.entferneErgaenzung(item.e)">Entfernen</v-btn></div>
            </div>
          </template>
        </v-virtual-scroll>
        <div v-else class="leer-hinweis">Keine Positionen für diesen Filter.</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import BaumZeile from '@/components/BaumZeile.vue'
import { IM_ERGEBNIS, OFFEN_STATUS, fmtDatum, fmtMenge, fmtZeit, mehrzahl } from '@/utils/texte'

const a = useArbeit()
const ui = useUi()
const d = computed(() => a.daten as any)
const rs = computed(() => a.reviewStand)
const speichert = ref(false)
// Hinweis, wenn eine Anfrage ungewöhnlich lange dauert (Server hängt, große Stückliste)
const langsam = ref(false)
let langsamTimer: number | undefined
watch(() => a.laedt, (l) => {
  clearTimeout(langsamTimer)
  langsam.value = false
  if (l) langsamTimer = window.setTimeout(() => { langsam.value = true }, 8000)
})
const exportLaedt = ref(false)
const scroller = ref<any>(null)
const baumEl = ref<HTMLElement | null>(null)

// Kennzahlen inkl. manueller Entscheidungen – so, wie das Material exportiert wird (D26)
const k = computed(() => a.kennzahlen)

const zeilen = computed(() => {
  const z: any[] = a.sichtbar.reihenfolge.map((x) => ({ art: 'pos', ...x }))
  if (a.ergaenzteZeilen.length) z.push({ art: 'titel' }, ...a.ergaenzteZeilen.map((e) => ({ art: 'erg', e })))
  return z
})

function umschalten(f: any) { a.filter = a.filter === f ? 'alle' : f }

function zeige(id: string) {
  a.zeigePosition(id)
  nextTick(() => scrolle(id))
}

function scrolle(id: string | null) {
  if (!id) return
  const i = zeilen.value.findIndex((z) => z.art === 'pos' && z.p.id === id)
  if (i >= 0) scroller.value?.scrollToIndex(Math.max(0, i - 3))
}

watch(() => a.auswahl, (id) => nextTick(() => {
  // nur scrollen, wenn die Zeile nicht sichtbar ist
  const el = baumEl.value?.querySelector(`[data-id="${CSS.escape(id || '')}"]`) as HTMLElement | null
  if (!el) scrolle(id)
}))

// nach einem Urteil per Tastatur zur nächsten Zeile
function weiter(ids: string[]) {
  const i = ids.indexOf(a.auswahl as string)
  if (i >= 0 && i < ids.length - 1) a.auswahl = ids[i + 1]
}

function taste(ev: KeyboardEvent) {
  if (['INPUT', 'TEXTAREA'].includes((ev.target as HTMLElement)?.tagName)) return
  const ids = a.sichtbar.reihenfolge.map((x) => x.p.id)
  const i = ids.indexOf(a.auswahl as string)
  if (ev.key === 'ArrowDown') { ev.preventDefault(); a.auswahl = ids[Math.min(ids.length - 1, i + 1)] ?? ids[0] }
  else if (ev.key === 'ArrowUp') { ev.preventDefault(); a.auswahl = ids[Math.max(0, i - 1)] ?? ids[0] }
  else if ((ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') && a.auswahl) { ev.preventDefault(); a.klappe(a.auswahl, ev.key === 'ArrowRight') }
  else if (a.auswahl && !a.bewertenGesperrt && (ev.key === 'f' || ev.key === 'F')) {
    ev.preventDefault()
    const p = a.sichtbar.reihenfolge.find((x) => x.p.id === a.auswahl)?.p
    if (!p) return
    const urteil = OFFEN_STATUS.has(p.status) ? 'gehoert_nicht_rein' : IM_ERGEBNIS.has(p.status) ? 'gehoert_nicht_rein' : 'fehlt'
    a.entscheide(p, urteil)
    weiter(ids)
  }
  else if (a.auswahl && !a.bewertenGesperrt && (ev.key === 'e' || ev.key === 'E')) {
    ev.preventDefault()
    const p = a.sichtbar.reihenfolge.find((x) => x.p.id === a.auswahl)?.p
    if (p && OFFEN_STATUS.has(p.status)) { a.entscheide(p, 'fehlt'); weiter(ids) }
  }
  else if (a.auswahl && !a.bewertenGesperrt && (ev.key === 'r' || ev.key === 'R')) {
    ev.preventDefault()
    const p = a.sichtbar.reihenfolge.find((x) => x.p.id === a.auswahl)?.p
    if (p && OFFEN_STATUS.has(p.status)) { ui.melde('„Manuell prüfen“ lässt sich nicht als „Richtig“ markieren – „Sollte rein“ (E) oder „Sollte raus“ (F) wählen.'); return }
    a.setzeUrteil(a.auswahl, 'richtig')  // setzt nur; Entfernen mit Entf/Rücktaste
    weiter(ids)
  }
  else if (a.auswahl && !a.bewertenGesperrt && (ev.key === 'Delete' || ev.key === 'Backspace')) {
    ev.preventDefault()
    a.setzeUrteil(a.auswahl, null)
  }
  else if (a.auswahl && a.bewertenGesperrt && ['r', 'R', 'f', 'F', 'e', 'E', 'Delete', 'Backspace'].includes(ev.key)) {
    ev.preventDefault()
    ui.melde(a.bewertenGesperrt)
    return
  }
  else return
  nextTick(() => {
    const el = baumEl.value?.querySelector(`[data-id="${CSS.escape(a.auswahl || '')}"]`) as HTMLElement | null
    if (el) el.scrollIntoView({ block: 'nearest' }); else scrolle(a.auswahl)
  })
}

async function speichere() {
  speichert.value = true
  try { await a.speichereReview() } catch (e) { ui.melde((e as Error).message, true) } finally { speichert.value = false }
}

async function verwerfeBewertung() {
  if (await ui.frage({ titel: 'Ungespeicherte Bewertungen verwerfen?', text: `${rs.value.ungespeichert} ungespeicherte Änderungen an den Bewertungen gehen verloren.`, ja: 'Verwerfen', gefahr: true })) a.bewertungVerwerfen()
}

async function bestaetige() {
  const ok = await ui.frage({
    titel: `Material ${d.value.matnr} bestätigen?`,
    text: 'Damit bestätigen Sie, dass die Basis-Stückliste so richtig ist. Sie dient danach als Referenz: ändert eine spätere Regeländerung dieses Material, wird das gemeldet.\n\nDie Bestätigung lässt sich jederzeit wieder aufheben.',
    ja: 'Bestätigen',
  })
  if (!ok) return
  try { await a.bestaetige() } catch (e) { ui.melde((e as Error).message, true) }
}

async function aufheben() {
  const ok = await ui.frage({ titel: 'Bestätigung aufheben?', text: `Material ${d.value.matnr} ist dann nicht mehr Referenz für spätere Läufe und kann wieder bewertet werden.`, ja: 'Aufheben' })
  if (!ok) return
  try { await a.bestaetigungAufheben() } catch (e) { ui.melde((e as Error).message, true) }
}

async function exportiere() {
  if (d.value.review?.bestaetigt?.veraltet) {
    const ok = await ui.frage({ titel: 'Bestätigung veraltet', text: 'Seit der Bestätigung haben Regeländerungen dieses Material verändert. Der Export zeigt den aktuellen Stand, nicht den bestätigten.', ja: 'Trotzdem exportieren' })
    if (!ok) return
  }
  if (!a.entwurfLeer || rs.value.ungespeichert) ui.melde('Hinweis: Der Export enthält den gespeicherten Stand – ohne Ihren Entwurf und ohne ungespeicherte Bewertungen.')
  exportLaedt.value = true
  try { await a.exportiere(d.value.matnr) } catch (e) { ui.melde((e as Error).message, true) } finally { exportLaedt.value = false }
}
</script>

<style scoped>
.stueckliste { flex: 1; min-height: 0; display: flex; flex-direction: column; position: relative; }
.kopf { padding: 14px 18px 10px; border-bottom: 1px solid var(--linie); flex: none; }
.titelzeile { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.mat-titel { font-size: 20px; font-weight: 700; letter-spacing: -0.015em; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mat-titel .kt { font-weight: 450; color: var(--text-2); font-size: 16px; }
.bestaetigt { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--s-basis); margin-top: 2px; }
.link { background: none; border: 0; color: var(--text-2); text-decoration: underline; cursor: pointer; font-size: 12px; }
.min-w-0 { min-width: 0; }
.kennzahlen { display: flex; gap: 8px; margin: 12px 0 10px; flex-wrap: wrap; }
.kennzahl { display: flex; flex-direction: column; align-items: flex-start; padding: 7px 14px 7px 12px; border: 1px solid var(--linie); border-left-width: 4px; border-radius: 8px; background: #fff; cursor: pointer; min-width: 150px; }
.kennzahl:hover { background: var(--hover); }
.kennzahl.aktiv { box-shadow: 0 0 0 2px rgba(0, 0, 0, .08) inset; background: var(--flaeche-2); }
.kennzahl .wert { font-size: 20px; font-weight: 700; line-height: 1.15; }
.kennzahl .wert small { font-size: 13px; color: var(--entwurf); }
.kennzahl .name { font-size: 12px; color: var(--text-2); }
.k-basis { border-left-color: var(--s-basis); } .k-offen { border-left-color: var(--s-manuell); } .k-aus { border-left-color: var(--s-aus); } .k-entwurf { border-left-color: var(--entwurf); }
.werkzeuge { display: flex; align-items: center; gap: 6px 8px; flex-wrap: wrap; }
.werkzeuge .klapp { display: flex; }
.segment :deep(.v-btn) { text-transform: none; letter-spacing: 0; }
.baum-suche { max-width: 220px; min-width: 160px; }
.hinweis-mehrzeilig { font-size: 13px; }
.review-leiste { display: flex; align-items: center; gap: 10px 12px; margin-top: 10px; padding: 8px 10px; border-radius: 8px; background: var(--flaeche-2); border: 1px solid var(--linie); flex-wrap: wrap; }
.fortschritt { flex: 1 1 180px; min-width: 160px; }
.knoepfe { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.fz { font-size: 12.5px; margin-bottom: 4px; display: flex; gap: 6px; flex-wrap: wrap; }
.ungespeichert { color: var(--s-manuell); font-weight: 550; }
.hinweis { font-size: 13px; }
.baum-kopf, :deep(.zeile) { display: grid; grid-template-columns: minmax(220px, 1fr) 96px 170px 184px; gap: 10px; align-items: center; padding: 0 18px; }
.baum-kopf { flex: none; height: 32px; font-size: 11px; font-weight: 650; letter-spacing: .05em; text-transform: uppercase; color: var(--text-3); border-bottom: 1px solid var(--linie); background: var(--flaeche-2); }
.r { text-align: right; }
.baum { flex: 1; min-height: 0; outline: none; }
.gruppen-titel { height: 50px; display: flex; align-items: flex-end; padding: 0 18px 6px; font-size: 11px; font-weight: 650; letter-spacing: .05em; text-transform: uppercase; color: var(--entwurf); border-bottom: 1px solid var(--linie); }
.ergaenzt { height: 50px; border-bottom: 1px solid var(--linie); background: #fbf9ff; }
.ergaenzt .name { display: flex; align-items: center; gap: 8px; min-width: 0; padding-left: 26px; }
.ergaenzt .kt { font-size: 12px; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ergaenzt .mat { font-weight: 600; font-size: 13px; }
.name-text { min-width: 0; }
.pkt { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.pkt-ergaenzt { background: var(--entwurf); }
.menge { text-align: right; font-size: 13px; }
.kennzahl .kurz { display: none; }
.btxt-kurz { display: none; }
.langsam { position: absolute; top: 8px; right: 12px; z-index: 3; max-width: 420px; }
@media (max-width: 1440px) {
  .baum-kopf, :deep(.zeile) { grid-template-columns: minmax(160px, 1fr) 76px 150px 112px; gap: 8px; padding: 0 12px; }
  .kopf { padding: 10px 12px 8px; }
  .mat-titel { font-size: 18px; }
  /* Kennzahlen als eine kompakte Zeile, damit der Baum Platz behält */
  .kennzahlen { margin: 8px 0; gap: 6px; flex-wrap: nowrap; }
  .kennzahl { min-width: 0; flex: 1 1 0; flex-direction: row; align-items: baseline; gap: 6px; padding: 4px 10px; }
  .kennzahl .wert { font-size: 16px; }
  .kennzahl .name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .kennzahl .lang { display: none; }
  .kennzahl .kurz { display: inline; }
  .sek .btxt { display: none; }
  .sek .btxt-kurz { display: inline; }
  .sek :deep(.v-btn__prepend) { margin-inline: 0 !important; }
  .werkzeuge { flex-wrap: nowrap; }
  .baum-suche { flex: 1 1 100px; min-width: 90px; max-width: 200px; }
  .segment :deep(.v-btn) { padding: 0 8px; }
  .review-leiste { margin-top: 8px; padding: 6px 8px; flex-wrap: nowrap; }
  .fortschritt { flex: 1 1 120px; }
  .fz { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
  .knoepfe { flex-wrap: nowrap; }
  .hinweis { padding-top: 4px !important; padding-bottom: 4px !important; font-size: 12.5px; }
}
</style>
