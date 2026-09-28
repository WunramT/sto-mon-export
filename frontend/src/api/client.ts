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
export function verbindeAuth(token: () => string | null, abmelden: () => void) {
  tokenQuelle = token
  beiAbmeldung = abmelden
}

const http = axios.create({ baseURL: apiBasis, timeout: 300000, headers: { 'Content-Type': 'application/json' } })

http.interceptors.request.use((config) => {
  const t = tokenQuelle()
  if (t) config.headers.Authorization = `Bearer ${t}`
  return config
})

function alsFehler(e: unknown): ApiFehler {
  const err = e as AxiosError<any>
  if (err.response) {
    const d = err.response.data || {}
    const text = typeof d.fehler === 'string' ? d.fehler : typeof d.detail === 'string' ? d.detail : `Fehler ${err.response.status}`
    return new ApiFehler(text, err.response.status, d)
  }
  if (err.code === 'ECONNABORTED') return new ApiFehler('Der Server antwortet nicht (Zeitüberschreitung).')
  return new ApiFehler('Server nicht erreichbar – bitte Verbindung prüfen.')
}

export async function api<T = any>(methode: string, url: string, body?: unknown): Promise<T> {
  try {
    const r = await http.request<T>({ method: methode, url, data: body })
    return r.data
  } catch (e) {
    const f = alsFehler(e)
    if (f.status === 401 && !url.startsWith('/auth/')) beiAbmeldung()
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
      try { throw new ApiFehler(JSON.parse(text).fehler || text, err.response.status) } catch (x) { if (x instanceof ApiFehler) throw x }
    }
    throw alsFehler(e)
  }
}
