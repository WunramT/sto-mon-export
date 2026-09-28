<template>
  <div class="karte" :class="{ hervor }" :data-merkmal="m.merkmal">
    <div class="kopf">
      <div class="min-w-0">
        <div class="mname">
          {{ a.mName(m.merkmal) }}
          <span v-if="a.mName(m.merkmal) !== m.merkmal" class="mcode mono">{{ m.merkmal }}</span>
          <button type="button" class="umbenennen" :aria-label="`Anzeigenamen für ${m.merkmal} ändern`" title="Anzeigenamen ändern"
            @click.stop="ui.oeffne('merkmalname', { merkmal: m.merkmal })"><v-icon icon="mdi-pencil-outline" size="13" /></button>
        </div>
        <div class="art">{{ art }}</div>
      </div>
      <span v-if="gewaehlt !== undefined" class="st" :class="gewaehlt && !vorlaeufig ? 'st-basis' : 'st-manuell_prüfen'"><span class="pkt" />{{ hierText }}</span>
    </div>
    <div v-if="m.frage" class="frage">
      <v-icon icon="mdi-help-circle-outline" size="15" />
      <span>{{ m.frage.text }}<span v-if="m.frage.beispiele?.length" class="bsp"> · z. B. in {{ m.frage.beispiele.map((b: string) => `„${b}“`).join(', ') }}</span></span>
    </div>
    <div class="werte">
      <div v-for="w in werte" :key="w.wert" class="wert-zeile" :class="{ 'im-entwurf': imEntwurf(w.wert), unbenutzt: unbenutzt(w) }"
        :title="w.beispiele?.length ? `Kommt vor in: ${w.beispiele.join(', ')}` : unbenutzt(w) ? 'Kommt in keiner Stückliste vor – keine Entscheidung nötig' : undefined">
        <div class="rang mono" :class="{ kein: w.status !== 'BASIS' }">
          <template v-if="w.status === 'BASIS' && !m.sitzhoehe && !m.systemregel">{{ w.rang }}</template>
          <template v-else-if="!m.systemregel">–</template>
        </div>
        <div class="wname">
          <span class="mono">{{ m.systemregel ? 'Gilt in der Basis?' : w.wert }}</span>
          <small v-if="hierWerte?.has(w.wert)" :class="{ gewaehlt: gewaehlt === w.wert }">{{ gewaehlt === w.wert ? (vorlaeufig ? '★ vorläufig gewählt' : '★ hier gewählt') : 'kommt hier vor' }}</small>
          <small v-else-if="w.stuecklisten">in {{ mehrzahl(w.stuecklisten, 'Stückliste', 'Stücklisten') }}</small>
          <small v-else-if="unbenutzt(w)">in keiner Stückliste</small>
          <small v-else-if="w.vorkommen">kommt im Material vor</small>
        </div>
        <div class="status-wahl" role="group" :aria-label="`Status für ${m.merkmal} ${w.wert}`">
          <button v-for="[st, text, cls] in knoepfe" :key="st" type="button" :class="[cls, { an: w.status === st }]" :aria-pressed="w.status === st"
            @click.stop="a.setzeStatus(m.merkmal, w.wert, st)">{{ text }}</button>
        </div>
        <div class="pfeile">
          <template v-if="w.status === 'BASIS' && basisWerte.length > 1 && !m.systemregel && !m.sitzhoehe">
            <button type="button" :disabled="index(w) <= 0" :aria-label="`${w.wert} Rang höher`" :title="`${w.wert} wichtiger machen`" @click.stop="a.verschiebe(m.merkmal, w.wert, -1)"><v-icon icon="mdi-chevron-up" size="16" /></button>
            <button type="button" :disabled="index(w) >= basisWerte.length - 1" :aria-label="`${w.wert} Rang tiefer`" :title="`${w.wert} weniger wichtig machen`" @click.stop="a.verschiebe(m.merkmal, w.wert, 1)"><v-icon icon="mdi-chevron-down" size="16" /></button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import { mehrzahl } from '@/utils/texte'

const props = defineProps<{ m: any; hierWerte?: Set<string> | null; gewaehlt?: string | null; hervor?: boolean; vorlaeufig?: boolean }>()
const a = useArbeit()
const ui = useUi()

const ord: Record<string, number> = { BASIS: 0, OFFEN: 1, NICHT_BASIS: 2 }
const basisWerte = computed(() => props.m.werte.filter((w: any) => w.status === 'BASIS').sort((x: any, y: any) => x.rang - y.rang))
const werte = computed(() => [...props.m.werte].sort((x: any, y: any) => ord[x.status] - ord[y.status] || (x.rang ?? 0) - (y.rang ?? 0) || String(x.wert).localeCompare(String(y.wert), 'de', { numeric: true })))
const index = (w: any) => basisWerte.value.findIndex((x: any) => x.wert === w.wert)
const imEntwurf = (w: string) => Boolean(a.entwurf.regeln[`${props.m.merkmal}|${w}`])
const unbenutzt = (w: any) => !props.hierWerte && w.stuecklisten === 0

const art = computed(() => {
  if (props.m.systemregel) return 'Technische Regel – gilt sie in der Basis?'
  if (props.m.sitzhoehe) return 'Automatisch: der niedrigste vorkommende Wert gewinnt'
  return basisWerte.value.length > 1 ? 'Mehrere Basiswerte: der kleinste Rang gewinnt. Reihenfolge mit ▲▼ ändern.' : 'Kommen mehrere Basiswerte vor, gewinnt der kleinste Rang.'
})
const knoepfe = computed(() => props.m.systemregel
  ? [['BASIS', 'Gilt', 'b'], ['OFFEN', 'Offen', 'o'], ['NICHT_BASIS', 'Gilt nicht', 'n']]
  : props.m.sitzhoehe ? [['OFFEN', 'Erlaubt', 'o'], ['NICHT_BASIS', 'Nie Basis', 'n']]
    : [['BASIS', 'Basis', 'b'], ['OFFEN', 'Offen', 'o'], ['NICHT_BASIS', 'Nie Basis', 'n']])
const hierText = computed(() => {
  if (props.m.systemregel) return props.gewaehlt ? 'hier: gilt' : 'hier: noch offen'
  if (props.gewaehlt && props.vorlaeufig) return `vorläufig ${props.gewaehlt}`
  return props.gewaehlt ? `hier gewählt: ${props.gewaehlt}` : 'hier: kein Basiswert'
})
</script>

<style scoped>
.karte { border: 1px solid var(--linie); border-radius: 10px; background: #fff; margin-bottom: 10px; overflow: hidden; transition: box-shadow .2s; }
.karte.hervor { box-shadow: 0 0 0 2px var(--auswahl-rand); }
.kopf { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; padding: 10px 12px 8px; }
.mname { font-weight: 650; font-size: 14px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.mcode { font-size: 11px; font-weight: 500; color: var(--text-3); background: var(--flaeche-2); padding: 0 5px; border-radius: 4px; }
.umbenennen { border: 0; background: transparent; color: var(--text-3); cursor: pointer; border-radius: 4px; padding: 1px 3px; }
.umbenennen:hover { color: var(--text-1); background: var(--hover); }
.art { font-size: 11.5px; color: var(--text-2); margin-top: 1px; }
.frage { display: flex; gap: 6px; align-items: flex-start; margin: 0 12px 8px; padding: 6px 8px; border-radius: 6px; background: var(--s-manuell-bg); color: #7a4a00; font-size: 12.5px; }
.bsp { color: #9a6a20; }
.wert-zeile { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto 44px; align-items: center; gap: 8px; padding: 6px 12px; border-top: 1px solid var(--linie); }
.wert-zeile.im-entwurf { background: var(--entwurf-bg); }
.wert-zeile.unbenutzt { opacity: .5; }
.rang { width: 22px; height: 22px; border-radius: 50%; background: var(--s-basis); color: #fff; font-size: 11.5px; font-weight: 700; display: grid; place-items: center; }
.rang.kein { background: transparent; color: var(--text-3); }
.wname { min-width: 0; display: flex; flex-direction: column; font-size: 13px; font-weight: 550; }
.wname small { font-size: 11px; font-weight: 400; color: var(--text-3); }
.wname small.gewaehlt { color: var(--s-basis); font-weight: 600; }
.status-wahl { display: inline-flex; border: 1px solid var(--linie-2); border-radius: 7px; overflow: hidden; }
.status-wahl button { border: 0; border-left: 1px solid var(--linie-2); background: #fff; padding: 4px 9px; font-size: 12px; cursor: pointer; color: var(--text-2); white-space: nowrap; }
.status-wahl button:first-child { border-left: 0; }
.status-wahl button:hover { background: var(--hover); }
.status-wahl button.an.b { background: var(--s-basis); color: #fff; }
.status-wahl button.an.o { background: #6b747c; color: #fff; }
.status-wahl button.an.n { background: #b3261e; color: #fff; }
.pfeile { display: flex; gap: 2px; justify-content: flex-end; }
.pfeile button { border: 1px solid var(--linie-2); background: #fff; border-radius: 5px; width: 20px; height: 22px; display: grid; place-items: center; cursor: pointer; padding: 0; }
.pfeile button:disabled { opacity: .35; cursor: default; }
.min-w-0 { min-width: 0; }
</style>
