// HTTP-Client: Basis-Pfad aus Vite (zur Laufzeit ersetzt, siehe entrypoint.sh), Token aus dem Auth-Store.
import axios, { AxiosError } from 'axios'

export const apiBasis = (import.meta.env.BASE_URL || '/').replace(/\/$/, '') + '/api'

export class ApiFehler extends Error {
  status?: number
  daten?: any
  constructor(text: string, status?: number, daten?: any) {
    super(text)
    this.status = status
    this.daten = daten
  }
}

let tokenQuelle: () => string | null = () => null
let beiAbmeldung: () => void = () => {}
let beiNichtBereit: () => void = () => {}
export function verbindeAuth(token: () => string | null, abmelden: () => void, nichtBereit?: () => void) {
  tokenQuelle = token
  beiAbmeldung = abmelden
  if (nichtBereit) beiNichtBereit = nichtBereit
}

// 60 s reichen für alles außer der Auswirkung über alle Materialien (dort eigenes Timeout)
const http = axios.create({ baseURL: apiBasis, timeout: 60000, headers: { 'Content-Type': 'application/json' } })

http.interceptors.request.use((config) => {
  const t = tokenQuelle()
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

function alsFehler(e: unknown): ApiFehler {
  const err = e as AxiosError<any>
  if (err.response) {
    const d = err.response.data || {}
    const standard: Record<number, string> = {
      429: 'Zu viele Anfragen – bitte kurz warten und erneut versuchen.',
      502: 'Das Backend ist gerade nicht erreichbar (Neustart?) – bitte gleich noch einmal versuchen.',
      504: 'Das Backend antwortet nicht rechtzeitig – bitte erneut versuchen.',
    }
    const text = typeof d.fehler === 'string' ? d.fehler : typeof d.detail === 'string' ? d.detail
      : standard[err.response.status] || `Unerwarteter Fehler (${err.response.status})`
    return new ApiFehler(text, err.response.status, d)
  }
  if (err.code === 'ECONNABORTED') return new ApiFehler('Der Server antwortet nicht (Zeitüberschreitung).')
  return new ApiFehler('Server nicht erreichbar – bitte Verbindung prüfen.')
}

export async function api<T = any>(methode: string, url: string, body?: unknown, timeout?: number): Promise<T> {
  try {
    const r = await http.request<T>({ method: methode, url, data: body, ...(timeout ? { timeout } : {}) })
    return r.data
  } catch (e) {
    const f = alsFehler(e)
    if (f.status === 401 && !url.startsWith('/auth/')) beiAbmeldung()
    if (f.status === 503 && !url.startsWith('/datenstand')) beiNichtBereit()
    throw f
  }
}

export async function herunterladen(url: string, dateiname: string): Promise<void> {
  try {
    const r = await http.get(url, { responseType: 'blob' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(r.data)
    link.download = dateiname
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(link.href), 1000)
  } catch (e) {
    const err = e as AxiosError<any>
    if (err.response?.data instanceof Blob) {
      const text = await err.response.data.text()
      let meldung = text || `Fehler ${err.response.status}`
      try { meldung = JSON.parse(text).fehler || meldung } catch { /* kein JSON: Text wie er ist */ }
      if (err.response.status === 401) beiAbmeldung()
      throw new ApiFehler(meldung, err.response.status)
    }
    throw alsFehler(e)
  }
}
