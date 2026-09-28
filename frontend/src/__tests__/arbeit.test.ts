import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: vi.fn(async () => ({})),
  herunterladen: vi.fn(),
  ApiFehler: class extends Error {},
}))

import { useArbeit } from '@/stores/arbeit'
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
})
