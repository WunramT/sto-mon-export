// Anzeigetexte und Formatierung – eine Stelle für alle Komponenten.

export const STATUS: Record<string, { text: string; kurz: string; hilfe: string }> = {
  basis: { text: 'Basis', kurz: 'Basis', hilfe: 'Erfüllt die Basis-Regeln – kommt in die Basis-Stückliste.' },
  unbedingt: { text: 'Immer enthalten', kurz: 'Immer', hilfe: 'Hat keine Variantenbedingung – immer dabei.' },
  manuell_prüfen: { text: 'Manuell prüfen', kurz: 'Prüfen', hilfe: 'Noch nicht entscheidbar, meist fehlt ein Basiswert. Unter „Offene Fragen“ steht, was fehlt.' },
  unterhalb_manuell: { text: 'Wartet auf Baugruppe', kurz: 'Wartet', hilfe: 'Die übergeordnete Baugruppe ist noch offen.' },
  ausgeschlossen: { text: 'Nicht in Basis', kurz: 'Nicht Basis', hilfe: 'Passt nicht zu den Basiswerten – kommt nicht in die Basis-Stückliste.' },
  ausgeschlossen_vererbt: { text: 'Nicht in Basis (Baugruppe)', kurz: 'Nicht Basis', hilfe: 'Die übergeordnete Baugruppe ist nicht in der Basis.' },
  ignoriert: { text: 'Ignoriert (Text)', kurz: 'Ignoriert', hilfe: 'Text- oder Dokumentposition – gehört nie zur Stückliste.' },
}
export const STATUS_REIHENFOLGE = ['basis', 'unbedingt', 'manuell_prüfen', 'unterhalb_manuell', 'ausgeschlossen', 'ausgeschlossen_vererbt', 'ignoriert']

export const IM_ERGEBNIS = new Set(['basis', 'unbedingt'])
export const OFFEN_STATUS = new Set(['manuell_prüfen', 'unterhalb_manuell'])
export const RAUS = new Set(['ausgeschlossen', 'ausgeschlossen_vererbt', 'ignoriert'])
export const REGEL_STATUS: Record<string, string> = { BASIS: 'Basis', OFFEN: 'Offen', NICHT_BASIS: 'Nie Basis' }
export const POSTP: Record<string, string> = {
  L: 'Lagerposition', N: 'Nichtlagerposition', K: 'Klassenposition', T: 'Textposition', D: 'Dokument', R: 'Rohmaterial',
}
export const ZUSTAND: Record<string, { text: string; farbe: string; icon: string }> = {
  offen: { text: 'Zu prüfen', farbe: 'info', icon: 'mdi-circle-outline' },
  in_arbeit: { text: 'In Arbeit', farbe: 'warning', icon: 'mdi-progress-clock' },
  bestaetigt: { text: 'Bestätigt', farbe: 'success', icon: 'mdi-check-circle' },
  nicht_aufloesbar: { text: 'Nicht auflösbar', farbe: 'grey', icon: 'mdi-alert-circle-outline' },
}
export const URTEIL: Record<string, string> = { richtig: 'Richtig', gehoert_nicht_rein: 'Sollte raus', fehlt: 'Sollte rein' }

const zahl = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 3 })
export const fmtZahl = (n: number) => zahl.format(n)
export const fmtMenge = (m: number | null | undefined, me?: string | null) =>
  m === null || m === undefined ? '–' : `${zahl.format(m)} ${me || ''}`.trim()
export const fmtDatum = (d: string | null | undefined) => (d ? new Date(d).toLocaleDateString('de-DE') : '–')
export const fmtZeit = (d: string | null | undefined) =>
  d ? new Date(d).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }) : '–'
export const fmtGroesse = (b: number) =>
  b > 1e9 ? `${(b / 1e9).toLocaleString('de-DE', { maximumFractionDigits: 2 })} GB`
    : b > 1e6 ? `${(b / 1e6).toLocaleString('de-DE', { maximumFractionDigits: 1 })} MB`
      : `${Math.max(1, Math.round(b / 1e3))} KB`
export const mehrzahl = (n: number, eins: string, viele: string) => `${n} ${n === 1 ? eins : viele}`
