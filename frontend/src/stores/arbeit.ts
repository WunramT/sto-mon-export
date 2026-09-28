// Arbeitszustand: Materialliste, geöffnetes Material, Regel-Entwurf, Bewertungen, Regel- und Auswirkungsansicht.
// Alle Berechnungen macht der Server (basis_bom); hier nur Zustand, Entwurf und ungespeicherte Bewertungen.
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { api, apiBasis, ApiFehler, herunterladen } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useUi } from '@/stores/ui'
import { speicher } from '@/utils/speicher'
import { IM_ERGEBNIS, OFFEN_STATUS, RAUS, REGEL_STATUS, mehrzahl } from '@/utils/texte'

type Dict<T = any> = Record<string, T>
export type Ansicht = 'stueckliste' | 'regeln' | 'auswirkung'
export type BaumFilter = 'alle' | 'offen' | 'ergebnis' | 'unbewertet' | 'geaendert'

export const useArbeit = defineStore('arbeit', () => {
  const auth = useAuth()
  const ui = useUi()

  // ------------------------------------------------------------------------------------------ Zustand
  const meta = ref<Dict | null>(null)
  const datenstand = ref<Dict | null>(null)
  const materialien = ref<Dict[]>([])
  const materialienLaden = ref(false)
  const zustandFilter = ref('alle')
  const materialQ = ref('')

  const matnr = ref<string | null>(null)
  const daten = ref<Dict | null>(null)
  const laedt = ref(false)
  const auswahl = ref<string | null>(null)
  const fokusMerkmal = ref<string | null>(null)
  const ansicht = ref<Ansicht>('stueckliste')
  const filter = ref<BaumFilter>('alle')
  const baumQ = ref('')
  const zu = ref(new Set<string>())

  const entwurf = ref<{ regeln: Dict; aliasse: Dict }>(speicher.lies('bb.entwurf', { regeln: {}, aliasse: {} }))
  const basisRegeln = ref<Dict>({})
  const basisAliasse = ref<Dict>({})
  const merkmale = reactive<Dict>({})

  // ungespeicherte Bewertungen des geöffneten Materials
  const lokal = ref<Dict>({})
  const lokalErgaenzt = ref<Dict[]>([])
  const entfernt = ref<string[]>([])

  const regelnQ = ref('')
  const regelnNurOffen = ref(true)
  const regelnNurMaterial = ref(false)
  const regelDaten = ref<Dict | null>(null)
  const regelnLaedt = ref(false)
  const auswirkung = ref<Dict | null>(null)
  const auswirkungLaedt = ref(false)
  const gestartet = ref(false)
  const startFehler = ref<string | null>(null)

  // ------------------------------------------------------------------------------------------ Entwurf
  const entwurfListe = computed(() => [...Object.values(entwurf.value.regeln), ...Object.values(entwurf.value.aliasse)])
  const entwurfAnzahl = computed(() => entwurfListe.value.length)
  const entwurfLeer = computed(() => entwurfAnzahl.value === 0)
  const entwurfPayload = () => ({ regeln: Object.values(entwurf.value.regeln), aliasse: Object.values(entwurf.value.aliasse) })
  const mName = (m: string) => meta.value?.namen?.[m] || m

  // Entwurf je Name auf dem Server merken (anderer Rechner/Browser). Kurz entprellt; beim Verlassen der Seite sofort.
  let speicherTimer: number | undefined
  let serverStand = ''
  function entwurfAnServer(beimVerlassen = false) {
    clearTimeout(speicherTimer)
    speicherTimer = undefined
    if (!auth.name || !gestartet.value) return
    const body = JSON.stringify({ name: auth.name, entwurf: entwurf.value })
    if (body === serverStand) return
    serverStand = body
    if (beimVerlassen) {
      fetch(`${apiBasis}/entwurf`, { method: 'PUT', body, keepalive: true,
        headers: { 'Content-Type': 'application/json', ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}) } }).catch(() => {})
    } else {
      api('PUT', '/entwurf', JSON.parse(body)).catch(() => { serverStand = '' })
    }
  }
  function speichereLokal() {
    speicher.schreib('bb.entwurf', entwurf.value)
    if (matnr.value) speicher.schreib(`bb.review.${matnr.value}`, { lokal: lokal.value, ergaenzt: lokalErgaenzt.value, entfernt: entfernt.value })
    clearTimeout(speicherTimer)
    speicherTimer = window.setTimeout(() => entwurfAnServer(), 300)
  }
  window.addEventListener('pagehide', () => { if (speicherTimer !== undefined) entwurfAnServer(true) })

  function bereinigeEntwurf() {
    let n = 0
    for (const [key, e] of Object.entries(entwurf.value.regeln)) {
      const jetzt = basisRegeln.value[key] || { status: 'OFFEN', rang: null }
      if (jetzt.status === e.status && (jetzt.rang ?? null) === (e.rang ?? null)) { delete entwurf.value.regeln[key]; n++ }
    }
    for (const [key, e] of Object.entries(entwurf.value.aliasse)) {
      const jetzt = basisAliasse.value[key]
      if (jetzt && (jetzt.merkmal || null) === (e.merkmal || null) && jetzt.status === e.status) { delete entwurf.value.aliasse[key]; n++ }
    }
    return n
  }

  async function ladeServerEntwurf() {
    if (!auth.name) return
    try {
      const r = await api('GET', `/entwurf?name=${encodeURIComponent(auth.name)}`)
      if (r.entwurf) entwurf.value = { regeln: r.entwurf.regeln || {}, aliasse: r.entwurf.aliasse || {} }
      serverStand = JSON.stringify({ name: auth.name, entwurf: r.entwurf || { regeln: {}, aliasse: {} } })
    } catch { /* lokaler Stand bleibt */ }
  }

  function regelStatusText(status: string, rang: number | null, systemregel: boolean) {
    if (systemregel) return ({ BASIS: 'Gilt', OFFEN: 'Offen', NICHT_BASIS: 'Gilt nicht' } as Dict)[status]
    return status === 'BASIS' ? `Basis (Rang ${rang})` : REGEL_STATUS[status]
  }

  function entwurfEintragText(e: Dict) {
    if (e.alias) return `Kürzel ${e.alias} → ${e.merkmal ? mName(e.merkmal) : '–'}`
    const sys = e.wert === 'vorhanden'
    return `${mName(e.merkmal)}${sys ? '' : ` = ${e.wert}`}: ${regelStatusText(e.vorher.status, e.vorher.rang, sys)} → ${regelStatusText(e.status, e.rang, sys)}`
  }

  let neuRechnenTimer: number | undefined
  function entwurfGeaendert() {
    speichereLokal()
    auswirkung.value = null
    clearTimeout(neuRechnenTimer)
    neuRechnenTimer = window.setTimeout(async () => {
      const aufgaben: Promise<any>[] = []
      if (matnr.value) aufgaben.push(ladeMaterial(matnr.value, { behalteAuswahl: true }))
      if (ansicht.value === 'regeln') aufgaben.push(ladeRegelAnsicht())
      await Promise.all(aufgaben)
      if (ansicht.value === 'auswirkung' && !entwurfLeer.value) berechneAuswirkung()
    }, 150)
  }

  function merkmalAktuell(m: string) {
    return merkmale[m] || regelDaten.value?.merkmale.find((x: Dict) => x.merkmal === m) || null
  }

  function wendeAn(merkmal: string, werte: Dict[]) {
    // Ränge der Basis-Werte lückenlos 1..n; Entwurf = Abweichung vom übernommenen Stand
    const basis = werte.filter((w) => w.status === 'BASIS').sort((a, b) => (a.rang ?? 999) - (b.rang ?? 999))
    basis.forEach((w, i) => (w.rang = i + 1))
    for (const w of werte) {
      if (w.status !== 'BASIS') w.rang = null
      const key = `${merkmal}|${w.wert}`
      const vorher = basisRegeln.value[key] || { status: 'OFFEN', rang: null }
      if (vorher.status === w.status && (vorher.rang ?? null) === (w.rang ?? null)) delete entwurf.value.regeln[key]
      else entwurf.value.regeln[key] = { merkmal, wert: w.wert, status: w.status, rang: w.rang, vorher }
    }
    const m = merkmalAktuell(merkmal)
    if (m) m.werte = werte
    if (regelDaten.value) {
      const r = regelDaten.value.merkmale.find((x: Dict) => x.merkmal === merkmal)
      if (r && r !== m) r.werte = werte.map((w) => ({ ...(r.werte.find((x: Dict) => x.wert === w.wert) || {}), ...w }))
    }
    entwurfGeaendert()
  }

  function setzeStatus(merkmal: string, wert: string, status: string) {
    const m = merkmalAktuell(merkmal)
    if (!m) return
    const werte = m.werte.map((w: Dict) => ({ ...w }))
    const w = werte.find((x: Dict) => x.wert === wert)
    if (!w || w.status === status) return
    if (status === 'BASIS') w.rang = Math.max(0, ...werte.filter((x: Dict) => x.status === 'BASIS').map((x: Dict) => x.rang || 0)) + 1
    w.status = status
    wendeAn(merkmal, werte)
  }

  function verschiebe(merkmal: string, wert: string, richtung: number) {
    const m = merkmalAktuell(merkmal)
    const werte = m.werte.map((w: Dict) => ({ ...w }))
    const basis = werte.filter((w: Dict) => w.status === 'BASIS').sort((a: Dict, b: Dict) => a.rang - b.rang)
    const i = basis.findIndex((w: Dict) => w.wert === wert)
    const j = i + richtung
    if (i < 0 || j < 0 || j >= basis.length) return
    ;[basis[i].rang, basis[j].rang] = [basis[j].rang, basis[i].rang]
    wendeAn(merkmal, werte)
  }

  function setzeKuerzel(alias: string, merkmal: string | null, status: string) {
    const vorher = basisAliasse.value[alias] || { merkmal: null, status: 'OFFEN' }
    if ((vorher.merkmal || null) === (merkmal || null) && vorher.status === status) delete entwurf.value.aliasse[alias]
    else entwurf.value.aliasse[alias] = { alias, merkmal: merkmal || null, status, vorher }
    entwurfGeaendert()
  }

  function nimmZurueck(e: Dict) {
    const topf = e.alias ? entwurf.value.aliasse : entwurf.value.regeln
    const key = e.alias ? e.alias : `${e.merkmal}|${e.wert}`
    delete topf[key]
    entwurfGeaendert()
    ui.melde(`Zurückgenommen: ${entwurfEintragText(e)}`, false, { text: 'Rückgängig', tun: () => { topf[key] = e; entwurfGeaendert() } })
  }

  function verwerfen() {
    const alt = entwurf.value
    entwurf.value = { regeln: {}, aliasse: {} }
    entwurfGeaendert()
    entwurfAnServer()
    ui.melde('Entwurf verworfen.', false, { text: 'Rückgängig', tun: () => { entwurf.value = alt; entwurfGeaendert() } })
  }

  async function uebernehmen(begruendung: string) {
    await api('POST', '/uebernehmen', { entwurf: entwurfPayload(), von: auth.name, begruendung })
    entwurf.value = { regeln: {}, aliasse: {} }
    ui.melde('Übernommen – die Regeln gelten jetzt für alle.')
    await ladeBasisRegeln()
    entwurfGeaendert()
    ladeMeta()
    ladeMaterialien()
  }

  async function konfliktAufloesen(konflikte: Dict[]) {
    for (const k of konflikte) {
      if (k.art === 'regel') delete entwurf.value.regeln[`${k.merkmal}|${k.wert}`]
      else delete entwurf.value.aliasse[k.alias]
    }
    await ladeBasisRegeln()
    for (const e of Object.values(entwurf.value.regeln)) e.vorher = basisRegeln.value[`${e.merkmal}|${e.wert}`] || { status: 'OFFEN', rang: null }
    for (const e of Object.values(entwurf.value.aliasse)) e.vorher = basisAliasse.value[e.alias] || { merkmal: null, status: 'OFFEN' }
    entwurfGeaendert()
  }

  // ------------------------------------------------------------------------------------------ Laden
  async function ladeDatenstand() {
    datenstand.value = await api('GET', '/datenstand')
    return datenstand.value
  }

  async function ladeBasisRegeln() {
    const d = await api('POST', '/regeln', { entwurf: null })
    const r: Dict = {}
    for (const m of d.merkmale) for (const w of m.werte) r[`${m.merkmal}|${w.wert}`] = { status: w.status, rang: w.rang }
    basisRegeln.value = r
    const a: Dict = {}
    for (const k of d.kuerzel) a[k.alias] = { merkmal: k.merkmal, status: k.status }
    basisAliasse.value = a
  }

  async function ladeMeta() { meta.value = await api('GET', '/meta') }

  async function ladeMaterialien() {
    materialienLaden.value = true
    try { materialien.value = await api('GET', '/materialien') } finally { materialienLaden.value = false }
  }

  async function ladeMaterial(m: string, { behalteAuswahl = false } = {}) {
    const neu = m !== matnr.value
    matnr.value = m
    if (neu) {
      auswahl.value = null
      fokusMerkmal.value = null
      const r = speicher.lies<Dict>(`bb.review.${m}`, { lokal: {}, ergaenzt: [] })
      lokal.value = r.lokal || {}
      lokalErgaenzt.value = r.ergaenzt || []
      entfernt.value = r.entfernt || []
      daten.value = daten.value && daten.value.matnr === m ? daten.value : null
    }
    laedt.value = true
    try {
      const d = await api('POST', `/material/${m}`, { entwurf: entwurfPayload() })
      if (matnr.value !== m) return  // inzwischen anderes Material gewählt
      daten.value = d
      for (const x of d.merkmale) merkmale[x.merkmal] = x
      if (neu) {
        zu.value = new Set(d.positionen.filter((p: Dict) => p.hat_kinder && RAUS.has(p.status)).map((p: Dict) => p.id))
        filter.value = 'alle'
        baumQ.value = ''
      }
      if (!behalteAuswahl && neu) auswahl.value = null
    } catch (e) {
      if (matnr.value === m) daten.value = { fehler: (e as Error).message, matnr: m }
    } finally {
      if (matnr.value === m) laedt.value = false
    }
  }

  async function oeffneMaterial(m: string) {
    ansicht.value = 'stueckliste'
    await ladeMaterial(m)
  }

  async function start() {
    startFehler.value = null
    try {
      await Promise.all([ladeMeta(), ladeBasisRegeln(), ladeMaterialien(), ladeServerEntwurf()])
      const alt = bereinigeEntwurf()
      if (alt) {
        speichereLokal()
        ui.melde(`${alt} Änderung${alt === 1 ? ' war' : 'en waren'} schon übernommen und ${alt === 1 ? 'wurde' : 'wurden'} aus dem Entwurf entfernt.`)
      }
      gestartet.value = true
    } catch (e) {
      startFehler.value = (e as Error).message
    }
  }

  // ------------------------------------------------------------------------------------------ Baum
  function urteilVon(id: string) {
    if (lokal.value[id] !== undefined) return lokal.value[id]
    return daten.value?.review?.urteile?.[id] || null
  }

  const sichtbar = computed(() => {
    const d = daten.value
    if (!d?.positionen) return { reihenfolge: [] as { p: Dict; kontext: boolean }[], treffer: 0 }
    const q = baumQ.value.trim().toUpperCase()
    const passt = (p: Dict) => {
      if (q && !((p.matnr || '').includes(q) || (p.kurztext || '').toUpperCase().includes(q))) return false
      if (filter.value === 'offen') return OFFEN_STATUS.has(p.status)
      if (filter.value === 'ergebnis') return IM_ERGEBNIS.has(p.status)
      if (filter.value === 'geaendert') return Boolean(p.vorher)
      if (filter.value === 'unbewertet') return !urteilVon(p.id)
      return true
    }
    const gefiltert = filter.value !== 'alle' || Boolean(q)
    const nachId = new Map<string, Dict>(d.positionen.map((p: Dict) => [p.id, p]))
    const treffer = new Set<string>(d.positionen.filter(passt).map((p: Dict) => p.id))
    const zeigen = new Set(treffer)
    if (gefiltert) {
      for (const id of treffer) {
        let p = nachId.get(id)
        while (p && nachId.has(p.parent)) { zeigen.add(p.parent); p = nachId.get(p.parent) }
      }
    }
    const kinder = new Map<string, Dict[]>()
    for (const p of d.positionen) { if (!kinder.has(p.parent)) kinder.set(p.parent, []); kinder.get(p.parent)!.push(p) }
    const reihenfolge: { p: Dict; kontext: boolean }[] = []
    const lauf = (parent: string) => {
      for (const p of kinder.get(parent) || []) {
        if (!zeigen.has(p.id)) continue
        reihenfolge.push({ p, kontext: gefiltert && !treffer.has(p.id) })
        if (!zu.value.has(p.id) || gefiltert) lauf(p.id)
      }
    }
    lauf(d.matnr)
    return { reihenfolge, treffer: treffer.size }
  })

  function klappe(id: string, auf?: boolean) {
    const s = new Set(zu.value)
    const offen = auf ?? s.has(id)
    if (offen) s.delete(id); else s.add(id)
    zu.value = s
  }
  function alleAuf() { zu.value = new Set() }
  function alleZu() { zu.value = new Set((daten.value?.positionen || []).filter((p: Dict) => p.hat_kinder).map((p: Dict) => p.id)) }

  function zeigePosition(id: string, merkmal: string | null = null) {
    // Vorfahren aufklappen, Filter lösen, auswählen
    const s = new Set(zu.value)
    for (let x = id; x.includes('/'); x = x.slice(0, x.lastIndexOf('/'))) s.delete(x.slice(0, x.lastIndexOf('/')))
    zu.value = s
    if (filter.value !== 'alle' || baumQ.value) { filter.value = 'alle'; baumQ.value = '' }
    ansicht.value = 'stueckliste'
    auswahl.value = id
    fokusMerkmal.value = merkmal
  }

  // ------------------------------------------------------------------------------------------ Bewertung
  const reviewStand = computed(() => {
    const d = daten.value
    if (!d?.positionen) return { alle: 0, bewertet: 0, richtig: 0, ungespeichert: 0, ergaenzt: 0 }
    let bewertet = 0
    let richtig = 0
    for (const p of d.positionen) { const u = urteilVon(p.id); if (u) { bewertet++; if (u.urteil === 'richtig') richtig++ } }
    const ungespeichert = Object.keys(lokal.value).length + lokalErgaenzt.value.length + entfernt.value.length
    const ergaenzt = (d.review?.ergaenzt || []).filter((e: Dict) => !entfernt.value.includes(e.pfad)).length + lokalErgaenzt.value.length
    return { alle: d.positionen.length, bewertet, richtig, ungespeichert, ergaenzt }
  })

  const ergaenzteZeilen = computed(() => {
    const gespeichert = (daten.value?.review?.ergaenzt || []).filter((e: Dict) => !entfernt.value.includes(e.pfad))
    return [...gespeichert.map((e: Dict) => ({ ...e, lokal: false })), ...lokalErgaenzt.value.map((e, i) => ({ ...e, lokal: true, index: i }))]
  })

  function setzeUrteil(id: string, urteil: string | null) {
    const alt = daten.value?.review?.urteile?.[id]
    const l = { ...lokal.value }
    if (urteil === null) {
      if (alt) l[id] = null; else delete l[id]
    } else {
      const kommentar = l[id]?.kommentar ?? alt?.kommentar ?? null
      l[id] = { urteil, kommentar }
      if (alt && alt.urteil === urteil && (alt.kommentar || null) === (kommentar || null)) delete l[id]
    }
    lokal.value = l
    speichereLokal()
  }

  function setzeKommentar(id: string, kommentar: string) {
    const cur = urteilVon(id)
    lokal.value = { ...lokal.value, [id]: { urteil: cur?.urteil || 'richtig', kommentar: kommentar || null } }
    speichereLokal()
  }

  function alleSichtbarenRichtig() {
    let n = 0
    const l = { ...lokal.value }
    for (const { p, kontext } of sichtbar.value.reihenfolge) if (!kontext && !urteilVon(p.id)) { l[p.id] = { urteil: 'richtig', kommentar: null }; n++ }
    lokal.value = l
    speichereLokal()
    const versteckt = (daten.value?.positionen || []).filter((p: Dict) => !urteilVon(p.id)).length
    ui.melde(n ? `${mehrzahl(n, 'Zeile', 'Zeilen')} als „Richtig“ markiert – noch nicht gespeichert.` + (versteckt ? ` ${versteckt} zugeklappte oder ausgefilterte Zeilen sind noch ohne Urteil.` : '')
      : 'Alle angezeigten Zeilen haben schon ein Urteil.')
  }

  function ergaenze(e: Dict) {
    lokalErgaenzt.value = [...lokalErgaenzt.value, e]
    speichereLokal()
  }

  function entferneErgaenzung(e: Dict) {
    if (e.lokal) lokalErgaenzt.value = lokalErgaenzt.value.filter((_, i) => i !== e.index)
    else entfernt.value = [...entfernt.value, e.pfad]
    speichereLokal()
  }

  function bewertungVerwerfen() {
    lokal.value = {}
    lokalErgaenzt.value = []
    entfernt.value = []
    speichereLokal()
  }

  const sperrGrund = computed<{ text: string; ziel?: string } | null>(() => {
    const d = daten.value
    const rs = reviewStand.value
    if (!d?.positionen || d.review?.bestaetigt) return null
    if (!entwurfLeer.value) return { text: 'Erst den Entwurf übernehmen oder verwerfen.' }
    const ohne = d.positionen.filter((p: Dict) => !urteilVon(p.id))
    if (ohne.length && !rs.bewertet) return null
    if (ohne.length) return { text: `Noch ${mehrzahl(ohne.length, 'Zeile', 'Zeilen')} ohne Urteil.`, ziel: ohne[0].id }
    if (rs.ungespeichert) return { text: 'Erst speichern, dann bestätigen.' }
    const falsch = d.positionen.filter((p: Dict) => urteilVon(p.id)?.urteil !== 'richtig')
    if (falsch.length || rs.ergaenzt) {
      const teile = []
      if (falsch.length) teile.push(`${mehrzahl(falsch.length, 'Zeile', 'Zeilen')} als falsch markiert`)
      if (rs.ergaenzt) teile.push(`${mehrzahl(rs.ergaenzt, 'Material', 'Materialien')} ergänzt`)
      return { text: `${teile.join(', ')}. Regel anpassen und neu bewerten – oder so lassen: die Abweichung ist gespeichert.`, ziel: falsch[0]?.id }
    }
    if (d.review?.veraltet) return { text: `${mehrzahl(d.review.veraltet, 'Zeile hat', 'Zeilen haben')} seit der Bewertung einen anderen Status – bitte neu bewerten.` }
    return null
  })

  const bestaetigbar = computed(() => {
    const d = daten.value
    const rs = reviewStand.value
    if (!d?.positionen || rs.ungespeichert || !entwurfLeer.value || d.review?.veraltet || rs.ergaenzt) return false
    return d.positionen.every((p: Dict) => d.review?.urteile?.[p.id]?.urteil === 'richtig')
  })

  async function speichereReview() {
    const d = daten.value!
    const urteile: Dict = {}
    for (const p of d.positionen) { const u = urteilVon(p.id); if (u) urteile[p.id] = u }
    const ergaenzt = [
      ...(d.review?.ergaenzt || []).filter((e: Dict) => !entfernt.value.includes(e.pfad))
        .map((e: Dict) => ({ parent_pfad: e.pfad.split('/+:')[0], matnr: e.matnr, menge: e.menge, meins: e.meins, kommentar: e.kommentar })),
      ...lokalErgaenzt.value,
    ]
    const r = await api('POST', `/review/${d.matnr}`, { von: auth.name, urteile, ergaenzt })
    bewertungVerwerfen()
    const teile = []
    if (r.urteile) teile.push(`${mehrzahl(r.urteile, 'Zeile', 'Zeilen')} bewertet`)
    if (r.ergaenzt) teile.push(`${mehrzahl(r.ergaenzt, 'Material', 'Materialien')} als fehlend ergänzt`)
    ui.melde(`Gespeichert: ${teile.join(', ') || 'keine Bewertungen'}.`)
    await Promise.all([ladeMaterial(d.matnr, { behalteAuswahl: true }), ladeMaterialien()])
  }

  async function bestaetige() {
    const m = daten.value!.matnr
    await api('POST', `/bestaetigen/${m}`, { von: auth.name })
    ui.melde('Material bestätigt – es dient ab jetzt als Referenz für spätere Läufe.')
    await Promise.all([ladeMaterial(m, { behalteAuswahl: true }), ladeMaterialien()])
  }

  async function bestaetigungAufheben() {
    const m = daten.value!.matnr
    await api('DELETE', `/bestaetigen/${m}`)
    ui.melde('Bestätigung zurückgenommen.')
    await Promise.all([ladeMaterial(m, { behalteAuswahl: true }), ladeMaterialien()])
  }

  async function exportiere(m: string) {
    await herunterladen(`/export/${m}`, `${m}_sap_format.csv`)
  }

  // ------------------------------------------------------------------------------------------ Regeln, Auswirkung
  async function ladeRegelAnsicht() {
    regelnLaedt.value = true
    try {
      const d = await api('POST', `/regeln?q=${encodeURIComponent(regelnQ.value)}&nur_offen=${regelnNurOffen.value}`, { entwurf: entwurfPayload() })
      regelDaten.value = d
      for (const m of d.merkmale) if (!merkmale[m.merkmal] || !daten.value?.merkmale?.some((x: Dict) => x.merkmal === m.merkmal)) merkmale[m.merkmal] = m
    } catch (e) {
      ui.melde((e as Error).message, true)
    } finally {
      regelnLaedt.value = false
    }
  }

  async function berechneAuswirkung() {
    auswirkungLaedt.value = true
    try { auswirkung.value = await api('POST', '/auswirkung', { entwurf: entwurfPayload() }) } catch (e) { auswirkung.value = { fehler: (e as Error).message } } finally { auswirkungLaedt.value = false }
  }

  async function oeffneMerkmal(merkmal: string) {
    regelnQ.value = ''
    regelnNurOffen.value = false
    regelnNurMaterial.value = false
    fokusMerkmal.value = merkmal
    ansicht.value = 'regeln'
    await ladeRegelAnsicht()
  }

  async function setzeMerkmalName(merkmal: string, text: string) {
    await api('PUT', '/merkmalname', { merkmal, text })
    await ladeMeta()
    ui.melde('Anzeigename gespeichert.')
    if (matnr.value) ladeMaterial(matnr.value, { behalteAuswahl: true })
    if (ansicht.value === 'regeln') ladeRegelAnsicht()
  }

  // Zahl offener Regelfragen (mit Entwurf, wenn vorhanden)
  const offeneFragen = computed(() => {
    if (!entwurfLeer.value) return regelDaten.value?.offen ?? daten.value?.offen ?? meta.value?.offen ?? 0
    return meta.value?.offen ?? 0
  })

  return {
    meta, datenstand, materialien, materialienLaden, zustandFilter, materialQ, matnr, daten, laedt, auswahl, fokusMerkmal,
    ansicht, filter, baumQ, zu, entwurf, basisRegeln, basisAliasse, merkmale, lokal, lokalErgaenzt, entfernt,
    regelnQ, regelnNurOffen, regelnNurMaterial, regelDaten, regelnLaedt, auswirkung, auswirkungLaedt, gestartet, startFehler,
    entwurfListe, entwurfAnzahl, entwurfLeer, mName, entwurfEintragText, regelStatusText, setzeStatus, verschiebe, setzeKuerzel,
    nimmZurueck, verwerfen, uebernehmen, konfliktAufloesen, ladeDatenstand, ladeMeta, ladeMaterialien, ladeMaterial,
    oeffneMaterial, start, urteilVon, sichtbar, klappe, alleAuf, alleZu, zeigePosition, reviewStand, ergaenzteZeilen,
    setzeUrteil, setzeKommentar, alleSichtbarenRichtig, ergaenze, entferneErgaenzung, bewertungVerwerfen, sperrGrund,
    bestaetigbar, speichereReview, bestaetige, bestaetigungAufheben, exportiere, ladeRegelAnsicht, berechneAuswirkung,
    oeffneMerkmal, setzeMerkmalName, offeneFragen, ladeServerEntwurf, entwurfGeaendert, speichereLokal,
  }
})

export { ApiFehler }
