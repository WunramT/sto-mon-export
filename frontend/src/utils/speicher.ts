// localStorage mit Absicherung (privater Modus, volle Quote)
export const speicher = {
  lies<T>(k: string, standard: T): T {
    try { const v = localStorage.getItem(k); return v === null ? standard : JSON.parse(v) } catch { return standard }
  },
  schreib(k: string, v: unknown) { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* ignorieren */ } },
  entferne(k: string) { try { localStorage.removeItem(k) } catch { /* ignorieren */ } },
}
