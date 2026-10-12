import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'

vi.mock('@/api/client', () => ({
  api: vi.fn(async () => ({})),
  apiBasis: '/api',
  herunterladen: vi.fn(),
  ApiFehler: class extends Error { status?: number; daten?: any },
}))

import { api } from '@/api/client'
import { useArbeit } from '@/stores/arbeit'
import { useUi } from '@/stores/ui'
import MerkmalKarte from '@/components/MerkmalKarte.vue'
import QuelltextAnzeige from '@/components/QuelltextAnzeige.vue'

const karte = (werte: any[]) => mount(MerkmalKarte, {
  props: { m: { merkmal: 'FUNKTION', name: 'Funktion', systemregel: false, sitzhoehe: false, werte } },
  global: { stubs: { 'v-icon': true } },
})

describe('Fundstellen eines Werts', () => {
  beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); vi.mocked(api).mockClear() })

  it('lädt die Fundstellen mit dem Entwurf', async () => {
    const a = useArbeit()
    a.entwurf.aliasse.ZZ = { alias: 'ZZ', merkmal: 'SITZTIEFE', status: 'BASIS' }
    await a.ladeFundstellen('SITZQUALI', 'HR/XX')
    expect(api).toHaveBeenCalledWith('POST', '/fundstellen?merkmal=SITZQUALI&wert=HR%2FXX',
      { entwurf: { regeln: [], aliasse: [{ alias: 'ZZ', merkmal: 'SITZTIEFE', status: 'BASIS' }] } })
  })

  it('macht die Stücklisten-Zahl klickbar und kennzeichnet Werte ohne Vorkommen', async () => {
    const w = karte([
      { wert: 'VZMO', status: 'OFFEN', rang: null, stuecklisten: 0 },
      { wert: 'WA1', status: 'OFFEN', rang: null, stuecklisten: 3 },
      { wert: 'X', status: 'BASIS', rang: 1, stuecklisten: 2 },
    ])
    const zeilen = w.findAll('.wert-zeile')
    // vorkommende Werte vor denen ohne Vorkommen (gleicher Status)
    expect(zeilen.map((z) => z.find('.wname .mono').text())).toEqual(['X', 'WA1', 'VZMO'])
    expect(zeilen[2].classes()).toContain('unbenutzt')
    expect(zeilen[2].text()).toContain('kommt in den Daten nicht vor')
    expect(zeilen[2].findAll('.status-wahl button').length).toBe(3)  // Entscheidung bleibt bedienbar
    expect(zeilen[1].classes()).not.toContain('unbenutzt')
    expect(w.find('.kopf .ohne-daten').exists()).toBe(false)
    await zeilen[1].find('button.fund').trigger('click')
    expect(useUi().dialog).toEqual({ art: 'fundstellen', daten: { merkmal: 'FUNKTION', wert: 'WA1' } })
  })

  it('markiert ein Merkmal, von dem kein Wert in den Daten vorkommt', () => {
    const w = karte([{ wert: 'X', status: 'BASIS', rang: 1, stuecklisten: 0 }])
    expect(w.find('.kopf .ohne-daten').text()).toContain('Kein Wert dieses Merkmals kommt in den Daten vor')
    expect(w.find('button.fund').exists()).toBe(false)
  })
})

describe('Quelltext einer Bedingung', () => {
  it('zeigt den Quelltext (CUKN) oder den Hinweis auf den Rückfall', () => {
    const mit = mount(QuelltextAnzeige, { props: { text: "$parent.W_FUNKTION = 'X'." } })
    expect(mit.find('pre.quelltext').text()).toBe("$parent.W_FUNKTION = 'X'.")
    expect(mit.find('.rueckfall').exists()).toBe(false)
    const ohne = mount(QuelltextAnzeige, { props: { text: null } })
    expect(ohne.find('pre').exists()).toBe(false)
    expect(ohne.find('.rueckfall').text()).toBe('kein Quelltext in CUKN – aus dem Namen gelesen')
    // Prozeduren werden nicht gelesen – kein Rückfall-Hinweis
    expect(mount(QuelltextAnzeige, { props: { text: null, prozedur: true } }).find('.rueckfall').exists()).toBe(false)
  })
})
