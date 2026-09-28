// Meldungen (Snackbar), Dialoge und Bestätigungsabfragen – zentral, damit jede Komponente sie auslösen kann.
import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Meldung { id: number; text: string; fehler?: boolean; aktion?: { text: string; tun: () => void } }
export interface Rueckfrage { titel: string; text: string; ja: string; nein?: string; gefahr?: boolean; aufloesen: (ok: boolean) => void }

let zaehler = 0

export const useUi = defineStore('ui', () => {
  const meldung = ref<Meldung | null>(null)
  const meldungOffen = ref(false)
  // Offener Dialog: art bestimmt die Komponente, daten deren Eingaben
  const dialog = ref<{ art: string; daten?: any } | null>(null)
  const rueckfrage = ref<Rueckfrage | null>(null)

  function melde(text: string, fehler = false, aktion?: Meldung['aktion']) {
    meldung.value = { id: ++zaehler, text, fehler, aktion }
    meldungOffen.value = true
  }

  function oeffne(art: string, daten?: any) { dialog.value = { art, daten } }
  function schliesse() { dialog.value = null }

  function frage(r: Omit<Rueckfrage, 'aufloesen'>): Promise<boolean> {
    return new Promise((ok) => { rueckfrage.value = { ...r, aufloesen: (x) => { rueckfrage.value = null; ok(x) } } })
  }

  return { meldung, meldungOffen, dialog, rueckfrage, melde, oeffne, schliesse, frage }
})
