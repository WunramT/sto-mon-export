import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: vi.fn(async () => ({})),
  apiBasis: '/api',
  herunterladen: vi.fn(),
  ApiFehler: class extends Error { status?: number; daten?: any },
}))

import { api } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { useAuth } from '@/stores/auth'
import { fmtMenge, mehrzahl } from '@/utils/texte'

const pos = (id: string, parent: string, status: string, extra = {}) => ({
  id, parent, status, matnr: id.split('/').pop(), kurztext: '', ebene: id.split('/').length - 1, hat_kinder: false, ...extra,
})

describe('Texte', () => {
  it('formatiert Mengen und Mehrzahl deutsch', () => {
    expect(fmtMenge(1.5, 'ST')).toBe('1,5 ST')
    expect(fmtMenge(null)).toBe('–')
    expect(mehrzahl(1, 'Zeile', 'Zeilen')).toBe('1 Zeile')
    expect(mehrzahl(3, 'Zeile', 'Zeilen')).toBe('3 Zeilen')
  })
})

describe('Arbeitszustand', () => {
  beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()) })

  it('zeigt beim Filtern die Vorfahren als Kontext', () => {
    const a = useArbeit()
    a.daten = { matnr: 'R', positionen: [
      pos('R/A', 'R', 'basis', { hat_kinder: true }), pos('R/A/B', 'R/A', 'manuell_prüfen'), pos('R/C', 'R', 'ausgeschlossen'),
    ] } as any
    expect(a.sichtbar.reihenfolge.map((x) => x.p.id)).toEqual(['R/A', 'R/A/B', 'R/C'])
    a.filter = 'offen'
    expect(a.sichtbar.reihenfolge.map((x) => [x.p.id, x.kontext])).toEqual([['R/A', true], ['R/A/B', false]])
    a.filter = 'alle'
    a.klappe('R/A')
    expect(a.sichtbar.reihenfolge.map((x) => x.p.id)).toEqual(['R/A', 'R/C'])
  })

  it('vergibt Ränge lückenlos und hält den Entwurf als Abweichung', () => {
    const a = useArbeit()
    a.basisRegeln = { 'SQ|HR': { status: 'BASIS', rang: 1 } }
    a.merkmale.SQ = { merkmal: 'SQ', werte: [{ wert: 'HR', status: 'BASIS', rang: 1 }, { wert: 'FK', status: 'OFFEN', rang: null }] }
    a.setzeStatus('SQ', 'FK', 'BASIS')
    expect(a.entwurf.regeln['SQ|FK']).toMatchObject({ status: 'BASIS', rang: 2, vorher: { status: 'OFFEN', rang: null } })
    a.verschiebe('SQ', 'FK', -1)
    expect(a.entwurf.regeln['SQ|FK'].rang).toBe(1)
    expect(a.entwurf.regeln['SQ|HR']).toMatchObject({ rang: 2 })
    a.verschiebe('SQ', 'FK', 1)
    a.setzeStatus('SQ', 'FK', 'OFFEN')
    expect(a.entwurfLeer).toBe(true)
  })

  it('zählt Bewertungen und sperrt Bestätigen bis alles richtig und gespeichert ist', () => {
    const a = useArbeit()
    a.daten = { matnr: 'R', positionen: [pos('R/A', 'R', 'basis'), pos('R/B', 'R', 'ausgeschlossen')], review: { urteile: {}, ergaenzt: [] } } as any
    a.setzeUrteil('R/A', 'richtig')
    expect(a.reviewStand).toMatchObject({ alle: 2, bewertet: 1, ungespeichert: 1 })
    expect(a.sperrGrund?.text).toContain('1 Zeile ohne Urteil')
    expect(a.bestaetigbar).toBe(false)
    a.setzeUrteil('R/A', null)
    expect(a.reviewStand.ungespeichert).toBe(0)
  })
  it('lässt offene Positionen manuell entscheiden und erst dann bestätigen', () => {
    const a = useArbeit()
    a.daten = { matnr: 'R', positionen: [pos('R/A', 'R', 'basis'), pos('R/K', 'R', 'manuell_prüfen')],
      review: { urteile: { 'R/A': { urteil: 'richtig' }, 'R/K': { urteil: 'richtig' } }, ergaenzt: [] } } as any
    expect(a.bestaetigbar).toBe(false)  // „richtig“ ist für offene Positionen keine Entscheidung
    a.daten.review.urteile['R/K'] = { urteil: 'fehlt' }
    expect(a.bestaetigbar).toBe(true)
    a.setzeUrteil('R/A', 'gehoert_nicht_rein')
    expect(a.bestaetigbar).toBe(false)  // ungespeichert und falsch
  })
  it('verwirft beim Öffnen, was inzwischen gespeichert ist, und bei bestätigten Materialien alles', async () => {
    useAuth().setzeName('Test')
    localStorage.setItem('bb.review.R.Test', JSON.stringify({
      lokal: { 'R/A': { urteil: 'richtig', kommentar: null }, 'R/B': { urteil: 'fehlt', kommentar: null } },
      ergaenzt: [{ parent_pfad: 'R', matnr: '999', menge: 1 }], entfernt: [] }))
    const antwort = (bestaetigt: any) => ({ matnr: 'R', merkmale: [], positionen: [pos('R/A', 'R', 'basis'), pos('R/B', 'R', 'ausgeschlossen')],
      review: { stand: 't2', von: 'Kollegin', bestaetigt,
        urteile: { 'R/A': { urteil: 'richtig', kommentar: null, status: 'basis' }, 'R/B': { urteil: 'richtig', kommentar: null, status: 'ausgeschlossen' } },
        ergaenzt: [{ pfad: 'R/+:999', matnr: '999' }] } })
    vi.mocked(api).mockResolvedValueOnce(antwort(null))
    const a = useArbeit()
    await a.ladeMaterial('R')
    expect(Object.keys(a.lokal)).toEqual(['R/B'])          // R/A war schon gespeichert
    expect(a.lokalErgaenzt).toEqual([])                     // Ergänzung schon auf dem Server
    expect(a.konfliktZeilen['R/B']).toMatchObject({ von: 'Kollegin', urteil: 'richtig' })
    setActivePinia(createPinia())
    useAuth().setzeName('Test')
    vi.mocked(api).mockResolvedValueOnce(antwort({ von: 'X', datum: '2026-09-28' }))
    const b = useArbeit()
    await b.ladeMaterial('R')
    expect(b.reviewStand.ungespeichert).toBe(0)             // bestätigt → nichts Lokales mehr
  })

  it('Speichern gilt dem Material, auf dem es gestartet wurde', async () => {
    useAuth().setzeName('Test')
    const a = useArbeit()
    const d = (m: string) => ({ matnr: m, merkmale: [], positionen: [pos(`${m}/A`, m, 'basis')], review: { urteile: {}, ergaenzt: [], stand: null } })
    vi.mocked(api).mockResolvedValueOnce(d('R'))
    await a.ladeMaterial('R')
    a.setzeUrteil('R/A', 'richtig')
    let fertig: (v: any) => void = () => {}
    vi.mocked(api).mockImplementationOnce(() => new Promise((ok) => { fertig = ok }))  // POST /review hängt
    const speichern = a.speichereReview()
    vi.mocked(api).mockResolvedValueOnce(d('S'))
    await a.ladeMaterial('S')                                // Wechsel während des Speicherns
    a.setzeUrteil('S/A', 'richtig')
    fertig({ urteile: 1, ergaenzt: 0 })
    vi.mocked(api).mockResolvedValue([])
    await speichern
    expect(a.matnr).toBe('S')
    expect(a.daten?.matnr).toBe('S')
    expect(Object.keys(a.lokal)).toEqual(['S/A'])           // S bleibt ungespeichert
    expect(JSON.parse(localStorage.getItem('bb.review.R.Test')!).lokal).toEqual({})  // R abgehakt
  })
})
