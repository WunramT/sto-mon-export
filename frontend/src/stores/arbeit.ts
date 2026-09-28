// Arbeitszustand: Materialliste, geöffnetes Material, Regel-Entwurf, Bewertungen, Regel- und Auswirkungsansicht.
// Alle Berechnungen macht der Server (basis_bom); hier nur Zustand, Entwurf und ungespeicherte Bewertungen.
import { defineStore } from 'pinia'
import { computed, reactive, ref, watch } from 'vue'
import { api, apiBasis, ApiFehler, herunterladen } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useUi } from '@/stores/ui'
import { speicher } from '@/utils/speicher'
import { IM_ERGEBNIS, OFFEN_STATUS, RAUS, REGEL_STATUS, mehrzahl } from '@/utils/texte'

type Dict<T = any> = Record<string, T>
export type Ansicht = 'stueckliste' | 'regeln' | 'auswirkung'
export type BaumFilter = 'alle' | 'offen' | 'ergebnis' | 'raus' | 'unbewertet' | 'geaendert'

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

  // Browser-Speicher je Name: wechselt jemand am selben Rechner, sieht niemand fremde Entwürfe oder Bewertungen
  const schluessel = (was: string) => `bb.${was}.${auth.name || '_'}`
  const entwurf = ref<{ regeln: Dict; aliasse: Dict }>(speicher.lies(schluessel('entwurf'), { regeln: {}, aliasse: {} }))
  // Arbeitskontext der letzten Sitzung (einmal beim Start gelesen, danach laufend geschrieben)
  const startKontext = speicher.lies<Dict>(schluessel('kontext'), {})
  let kontextBereit = false
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
  function entwurfAnServer(beimVerlassen = false, name = auth.name) {
    clearTimeout(speicherTimer)
    speicherTimer = undefined
    if (!name || !gestartet.value) return
    const body = JSON.stringify({ name, entwurf: entwurf.value })
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
    speicher.schreib(schluessel('entwurf'), entwurf.value)
    if (matnr.value) speicher.schreib(schluessel(`review.${matnr.value}`), { lokal: lokal.value, ergaenzt: lokalErgaenzt.value, entfernt: entfernt.value })
    clearTimeout(speicherTimer)
    const name = auth.name  // beim Planen festhalten: ein Namenswechsel darf den Entwurf nicht mitnehmen
    speicherTimer = window.setTimeout(() => entwurfAnServer(false, name), 300)
  }
  // sofort sichern (vor Namenswechsel/Abmelden), solange Name und Token noch gelten
  function entwurfSofortSichern() {
    speicher.schreib(schluessel('entwurf'), entwurf.value)
    if (speicherTimer !== undefined) entwurfAnServer(true)
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

  function wendeAn(merkmal: string, werte: Dict[], neuRechnen = true) {
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
    if (neuRechnen) entwurfGeaendert()
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
    if (!m) return
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
    await Promise.all([ladeBasisRegeln(), ladeMeta()])
    for (const e of Object.values(entwurf.value.regeln)) e.vorher = basisRegeln.value[`${e.merkmal}|${e.wert}`] || { status: 'OFFEN', rang: null }
    for (const e of Object.values(entwurf.value.aliasse)) e.vorher = basisAliasse.value[e.alias] || { merkmal: null, status: 'OFFEN' }
    // Ränge je betroffenem Merkmal neu durchnummerieren (übernommener Stand + verbliebener Entwurf)
    const betroffen = new Set([...konflikte.filter((k) => k.art === 'regel').map((k) => k.merkmal), ...Object.values(entwurf.value.regeln).map((e: Dict) => e.merkmal)])
    for (const m of betroffen) {
      const werte: Dict = {}
      for (const [key, r] of Object.entries(basisRegeln.value)) { const [mm, w] = key.split('|'); if (mm === m) werte[w] = { wert: w, status: r.status, rang: r.rang } }
      for (const e of Object.values(entwurf.value.regeln)) if (e.merkmal === m) werte[e.wert] = { wert: e.wert, status: e.status, rang: e.rang }
      wendeAn(m, Object.values(werte), false)
    }
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

  async function ladeMeta() { meta.value = await api('GET', '/meta'); regelnVeraltet.value = false }

  // Haben Kolleg:innen inzwischen Regeln übernommen? (Abfrage alle 30 s und beim Zurückkehren ins Fenster)
  const regelnVeraltet = ref(false)
  async function pruefeRegelstand() {
    if (!gestartet.value || !meta.value) return
    try {
      const m = await api('GET', '/meta')
      if (m.regel_version !== meta.value.regel_version) regelnVeraltet.value = true
    } catch { /* still: nächster Versuch */ }
  }
  async function aktualisiereRegeln() {
    await Promise.all([ladeBasisRegeln(), ladeMeta(), ladeMaterialien()])
    const n = bereinigeEntwurf()
    entwurfGeaendert()
    ui.melde('Regelstand aktualisiert.' + (n ? ` ${mehrzahl(n, 'Änderung Ihres Entwurfs war', 'Änderungen Ihres Entwurfs waren')} inzwischen übernommen und ${n === 1 ? 'wurde' : 'wurden'} entfernt.` : ''))
  }

  async function ladeMaterialien() {
    materialienLaden.value = true
    try { materialien.value = await api('GET', '/materialien') } finally { materialienLaden.value = false }
  }

  async function ladeMaterial(m: string, _opts: { behalteAuswahl?: boolean } = {}) {
    const neu = m !== matnr.value
    matnr.value = m
    if (neu) {
      auswahl.value = null
      fokusMerkmal.value = null
      const r = speicher.lies<Dict>(schluessel(`review.${m}`), { lokal: {}, ergaenzt: [] })
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
        // Arbeitskontext nach Neuladen der Seite wiederherstellen (Auswahl, Filter) – nur beim ersten Material
        const k = !kontextBereit && startKontext.matnr === m ? startKontext : {}
        filter.value = k.filter || 'alle'
        baumQ.value = ''
        if (k.auswahl && d.positionen.some((p: Dict) => p.id === k.auswahl)) {
          const z = new Set(zu.value)
          for (let x = k.auswahl; x.includes('/'); x = x.slice(0, x.lastIndexOf('/'))) z.delete(x.slice(0, x.lastIndexOf('/')))
          zu.value = z
          auswahl.value = k.auswahl
        }
        kontextBereit = true
      }
    } catch (e) {
      if (e instanceof ApiFehler && e.status === 503) { daten.value = null; return }
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
      if (startKontext.ansicht && ['regeln', 'auswirkung'].includes(startKontext.ansicht)) ansicht.value = startKontext.ansicht
    } catch (e) {
      startFehler.value = (e as Error).message
    }
  }

  // ------------------------------------------------------------------------------------------ Baum
  const statusNachId = computed(() => new Map<string, string>((daten.value?.positionen || []).map((p: Dict) => [p.id, p.status])))
  function urteilVon(id: string) {
    if (lokal.value[id] !== undefined) return lokal.value[id]
    const u = daten.value?.review?.urteile?.[id]
    // gespeichertes Urteil gilt nur, solange die Position noch denselben Status hat (sonst „veraltet“)
    if (u && u.status && statusNachId.value.get(id) && u.status !== statusNachId.value.get(id)) return null
    return u || null
  }
  // gespeichertes Urteil, das wegen einer Regeländerung nicht mehr gilt (zur Anzeige „war: …“)
  function altesUrteil(id: string) {
    if (lokal.value[id] !== undefined) return null
    const u = daten.value?.review?.urteile?.[id]
    return u && u.status && u.status !== statusNachId.value.get(id) ? u : null
  }
  // Abweichungen nach einem Speicherkonflikt: Urteil der Kollegin/des Kollegen je Zeile
  const konfliktZeilen = ref<Dict>({})

  const sichtbar = computed(() => {
    const d = daten.value
    if (!d?.positionen) return { reihenfolge: [] as { p: Dict; kontext: boolean }[], treffer: 0 }
    const q = baumQ.value.trim().toUpperCase()
    const passt = (p: Dict) => {
      if (q && !((p.matnr || '').includes(q) || (p.kurztext || '').toUpperCase().includes(q))) return false
      if (filter.value === 'offen') return OFFEN_STATUS.has(p.status)
      if (filter.value === 'ergebnis') return IM_ERGEBNIS.has(p.status)
      if (filter.value === 'geaendert') return Boolean(p.vorher)
      if (filter.value === 'raus') return RAUS.has(p.status)
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
        if (!zu.value.has(p.id)) lauf(p.id)
      }
    }
    lauf(d.matnr)
    return { reihenfolge, treffer: treffer.size }
  })

  // Beim Filtern/Suchen die Baugruppen über den Treffern aufklappen; danach wirkt Zuklappen wie gewohnt
  function klappeTrefferAuf() {
    const d = daten.value
    if (!d?.positionen || (filter.value === 'alle' && !baumQ.value.trim())) return
    const q = baumQ.value.trim().toUpperCase()
    const s = new Set(zu.value)
    for (const p of d.positionen) {
      const treffer = (!q || (p.matnr || '').includes(q) || (p.kurztext || '').toUpperCase().includes(q)) &&
        (filter.value === 'alle' || (filter.value === 'offen' ? OFFEN_STATUS.has(p.status) : filter.value === 'ergebnis' ? IM_ERGEBNIS.has(p.status)
          : filter.value === 'raus' ? RAUS.has(p.status) : filter.value === 'geaendert' ? Boolean(p.vorher) : !urteilVon(p.id)))
      if (!treffer) continue
      for (let x = p.parent; x.includes('/'); x = x.slice(0, x.lastIndexOf('/'))) s.delete(x)
    }
    zu.value = s
  }
  watch([filter, baumQ], klappeTrefferAuf)

  function klappe(id: string, auf?: boolean) {
    const s = new Set(zu.value)
    const offen = auf ?? s.has(id)
    if (offen) s.delete(id); else s.add(id)
    zu.value = s
  }
  function alleAuf() { zu.value = new Set() }
  function alleZu() { zu.value = new Set((daten.value?.positionen || []).filter((p: Dict) => p.hat_kinder).map((p: Dict) => p.id)) }

  function zeigePosition(id: string, merkmal: string | null = null, zurStueckliste = true) {
    // Vorfahren aufklappen, Filter lösen, auswählen
    const s = new Set(zu.value)
    for (let x = id; x.includes('/'); x = x.slice(0, x.lastIndexOf('/'))) s.delete(x.slice(0, x.lastIndexOf('/')))
    zu.value = s
    if (filter.value !== 'alle' || baumQ.value) { filter.value = 'alle'; baumQ.value = '' }
    if (zurStueckliste) ansicht.value = 'stueckliste'
    auswahl.value = id
    fokusMerkmal.value = merkmal
  }

  watch([matnr, auswahl, filter, ansicht], () => {
    if (matnr.value && kontextBereit) speicher.schreib(schluessel('kontext'), { matnr: matnr.value, auswahl: auswahl.value, filter: filter.value, ansicht: ansicht.value })
  })

  // Bestätigte Materialien sind gesperrt, bis die Bestätigung aufgehoben wird; mit Entwurf wird nicht bewertet
  const bewertenGesperrt = computed<string | null>(() => {
    if (!entwurfLeer.value) return 'Erst den Entwurf übernehmen oder verwerfen – bewertet wird der gespeicherte Regelstand.'
    if (daten.value?.review?.bestaetigt) return 'Das Material ist bestätigt. Zum Ändern zuerst die Bestätigung aufheben.'
    return null
  })

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

  // Urteil setzen wie per Knopf – Klassenposition „rein“ fragt nach dem eingesetzten Material
  function entscheide(p: Dict, urteil: string | null) {
    setzeUrteil(p.id, urteil)
    if (urteil === 'fehlt' && !p.matnr && p.postp === 'K' && klasseOhneMaterial(p)) {
      ui.oeffne('ergaenzen', { parentId: p.id, klasseId: p.id, hinweis: `Welches Material wird für die Klassenposition ${p.posnr} eingesetzt?` })
    }
  }

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
    if (!cur?.urteil) return  // Kommentar gehört zu einem Urteil (Feld ist ohne Urteil gesperrt)
    const alt = daten.value?.review?.urteile?.[id]
    const l = { ...lokal.value, [id]: { urteil: cur.urteil, kommentar: kommentar || null } }
    if (alt && alt.urteil === cur.urteil && (alt.kommentar || null) === (kommentar || null)) delete l[id]
    lokal.value = l
    speichereLokal()
  }

  function alleSichtbarenRichtig() {
    let n = 0
    const l = { ...lokal.value }
    let offen = 0
    for (const { p, kontext } of sichtbar.value.reihenfolge) {
      if (kontext || urteilVon(p.id)) continue
      if (OFFEN_STATUS.has(p.status)) { offen++; continue }  // „Manuell prüfen“ ist nie einfach „richtig“
      l[p.id] = { urteil: 'richtig', kommentar: null }; n++
    }
    lokal.value = l
    speichereLokal()
    const versteckt = (daten.value?.positionen || []).filter((p: Dict) => !urteilVon(p.id)).length
    const text = n ? `${mehrzahl(n, 'Zeile', 'Zeilen')} als „Richtig“ markiert – noch nicht gespeichert.` : 'Keine weiteren Zeilen zum Markieren.'
    const zusatz = [
      offen ? `${mehrzahl(offen, 'Position „Manuell prüfen“ bleibt', 'Positionen „Manuell prüfen“ bleiben')} offen – dort „Sollte rein/raus“ entscheiden oder die Regelfrage klären.` : '',
      versteckt - offen > 0 ? `${mehrzahl(versteckt - offen, 'zugeklappte oder ausgefilterte Zeile ist', 'zugeklappte oder ausgefilterte Zeilen sind')} noch ohne Urteil.` : '',
    ].filter(Boolean).join(' ')
    ui.melde(zusatz ? `${text} ${zusatz}` : text)
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

  // Manuelle Entscheidung einer offenen Position (D25): gespeichert oder ungespeichert
  function manuell(p: Dict): 'rein' | 'raus' | null {
    if (!OFFEN_STATUS.has(p.status)) return null
    const u = urteilVon(p.id)?.urteil
    return u === 'fehlt' ? 'rein' : u === 'gehoert_nicht_rein' ? 'raus' : null
  }
  // „rein“ unter einer Baugruppe, die nicht in die Basis kommt (Regel oder manuell „raus“)
  const rausPfade = computed<string[]>(() => (daten.value?.positionen || [])
    .filter((p: Dict) => manuell(p) === 'raus' || (!OFFEN_STATUS.has(p.status) && !IM_ERGEBNIS.has(p.status))).map((p: Dict) => p.id))
  const unterRaus = (pfad: string, auchSelbst = false) => rausPfade.value.some((r) => pfad.startsWith(r + '/') || (auchSelbst && pfad === r))
  const widersprueche = computed<string[]>(() => {
    const ps: Dict[] = daten.value?.positionen || []
    const pos = ps.filter((p) => manuell(p) === 'rein' && unterRaus(p.id)).map((p) => p.id)
    // ergänzte Materialien unter einer Baugruppe, die nicht in die Basis kommt
    const erg = ergaenzteZeilen.value.map((e: Dict) => e.parent_pfad || e.pfad.split('/+:')[0]).filter((pp: string) => unterRaus(pp, true))
    return [...pos, ...erg]
  })
  // Klassenposition „rein“ ohne ergänztes Material unter derselben Baugruppe
  function klasseOhneMaterial(p: Dict) {
    if (p.matnr || p.postp !== 'K' || manuell(p) !== 'rein') return false
    return !ergaenzteZeilen.value.some((e: Dict) => (e.parent_pfad || e.pfad.split('/+:')[0]) === p.id)
  }
  // Kennzahlen wie im Export (D26): Regelergebnis + manuelle Entscheidungen + Ergänzungen
  const kennzahlen = computed(() => {
    const ps: Dict[] = daten.value?.positionen || []
    let basis = 0, offen = 0, aus = 0
    for (const p of ps) {
      const m = manuell(p)
      if (IM_ERGEBNIS.has(p.status) && !unterRaus(p.id) || (m === 'rein' && p.matnr && !unterRaus(p.id))) basis++
      else if (OFFEN_STATUS.has(p.status) && !m) offen++
      else aus++
    }
    const ergaenzt = ergaenzteZeilen.value.filter((e: Dict) => !unterRaus(e.parent_pfad || e.pfad.split('/+:')[0], true)).length
    return { basis, offen, aus, ergaenzt }
  })

  // Bestätigbar (D25): regelentschiedene Zeilen „richtig“, offene Zeilen manuell „Sollte rein/raus“
  function urteilPasst(p: Dict, u: Dict | null = urteilVon(p.id)) {
    if (!u?.urteil) return false
    if (klasseOhneMaterial(p)) return false
    return OFFEN_STATUS.has(p.status) ? u.urteil === 'fehlt' || u.urteil === 'gehoert_nicht_rein' : u.urteil === 'richtig'
  }

  const sperrGrund = computed<{ text: string; ziel?: string } | null>(() => {
    const d = daten.value
    const rs = reviewStand.value
    if (!d?.positionen || d.review?.bestaetigt) return null
    if (!entwurfLeer.value) return { text: 'Erst den Entwurf übernehmen oder verwerfen.' }
    if (d.review?.veraltet && !rs.ungespeichert) return null  // eigener Hinweis „Regeln geändert – neu bewerten“
    if (widersprueche.value.length) {
      return { text: `${mehrzahl(widersprueche.value.length, 'Position ist', 'Positionen sind')} „Sollte rein“, ihre Baugruppe aber nicht in der Basis – bitte eines von beiden ändern.`, ziel: widersprueche.value[0] }
    }
    const klasse = d.positionen.find((p: Dict) => klasseOhneMaterial(p))
    if (klasse) return { text: `Klassenposition ${klasse.posnr}: „Sollte rein“ braucht das eingesetzte Material – bitte über „Ergänzen“ eintragen.`, ziel: klasse.id }
    const ohne = d.positionen.filter((p: Dict) => !urteilVon(p.id))
    if (ohne.length && !rs.bewertet) return null
    if (ohne.length) return { text: `Noch ${mehrzahl(ohne.length, 'Zeile', 'Zeilen')} ohne Urteil.`, ziel: ohne[0].id }
    if (rs.ungespeichert) return { text: 'Erst speichern, dann bestätigen.' }
    const falsch = d.positionen.filter((p: Dict) => !urteilPasst(p))
    if (falsch.length) {
      return { text: `${mehrzahl(falsch.length, 'Zeile ist', 'Zeilen sind')} als falsch markiert – die Regel anpassen oder die Position manuell entscheiden. Die Abweichung ist gespeichert und dient als Hinweis für die Regeln.`, ziel: falsch[0]?.id }
    }
    return null
  })

  const bestaetigbar = computed(() => {
    const d = daten.value
    const rs = reviewStand.value
    if (!d?.positionen || rs.ungespeichert || !entwurfLeer.value || d.review?.veraltet || widersprueche.value.length) return false
    return d.positionen.every((p: Dict) => urteilPasst(p, d.review?.urteile?.[p.id]))
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
    const gesendet = { lokal: { ...lokal.value }, ergaenzt: [...lokalErgaenzt.value], entfernt: [...entfernt.value] }
    let r: Dict
    try {
      r = await api('POST', `/review/${d.matnr}`, { von: auth.name, urteile, ergaenzt, stand: d.review?.stand ?? null })
    } catch (e) {
      if (e instanceof ApiFehler && e.status === 409) {
        // Stand der Kollegin laden; die eigenen ungespeicherten Urteile bleiben darüber liegen
        await ladeMaterial(d.matnr, { behalteAuswahl: true })
        const wer = e.daten?.konflikte?.[0]?.von || 'Jemand'
        const kz: Dict = {}
        for (const [id, u] of Object.entries(lokal.value)) {
          const ihr = daten.value?.review?.urteile?.[id]
          if (ihr && ihr.urteil !== (u as Dict)?.urteil) kz[id] = { von: wer, urteil: ihr.urteil }
        }
        konfliktZeilen.value = kz
        const abweichend = Object.keys(kz).length
        throw new ApiFehler(`${wer} hat dieses Material inzwischen bewertet.` + (abweichend
          ? ` Bei ${mehrzahl(abweichend, 'Zeile weicht', 'Zeilen weichen')} Ihr Urteil von dem der Kollegin/des Kollegen ab – Ihres gilt, wenn Sie erneut speichern.`
          : ' Ihre Urteile liegen jetzt über deren Stand – bitte kurz prüfen und erneut speichern.'), 409)
      }
      throw e
    }
    konfliktZeilen.value = {}
    // nur das Gesendete als gespeichert abhaken – was während des Speicherns dazukam, bleibt offen
    const rest = { ...lokal.value }
    for (const [id, u] of Object.entries(gesendet.lokal)) if (JSON.stringify(rest[id]) === JSON.stringify(u)) delete rest[id]
    lokal.value = rest
    lokalErgaenzt.value = lokalErgaenzt.value.filter((e) => !gesendet.ergaenzt.includes(e))
    entfernt.value = entfernt.value.filter((x) => !gesendet.entfernt.includes(x))
    speichereLokal()
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
    try { auswirkung.value = await api('POST', '/auswirkung', { entwurf: entwurfPayload() }, 300000) } catch (e) { auswirkung.value = { fehler: (e as Error).message } } finally { auswirkungLaedt.value = false }
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
    oeffneMerkmal, setzeMerkmalName, offeneFragen, ladeServerEntwurf, entwurfGeaendert, speichereLokal, bewertenGesperrt,
    entwurfSofortSichern, urteilPasst, manuell, klasseOhneMaterial, unterRaus, altesUrteil, konfliktZeilen, entscheide, widersprueche, kennzahlen, regelnVeraltet, pruefeRegelstand,
    aktualisiereRegeln, startKontext,
    klappeTrefferAuf,
  }
})

export { ApiFehler }
