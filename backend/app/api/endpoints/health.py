from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request, db: bool = False):
    """Liveness für Docker: gesund, sobald der Prozess läuft – auch während die Daten laden.

    `?db=1` (Jenkins nach dem Start): zusätzlich Verbindung zur Datenbank prüfen und den Fehler lesbar melden.
    """
    ds = getattr(request.app.state, "datenstand", None)
    antwort = {"status": "ok", "daten": ds.status.zustand if ds else None}
    if db and ds is not None:
        try:
            with ds.eng.connect() as con:
                con.execute(sa.text("SELECT 1"))
            antwort["db"] = "ok"
        except Exception as exc:  # noqa: BLE001 - Meldung für den Betrieb
            antwort["db"] = "fehler"
            antwort["db_fehler"] = db_fehlertext(exc)
    return antwort


def db_fehlertext(exc: Exception) -> str:
    """Häufige Einrichtungsfehler in Klartext (sens.env / Datenbank-Rolle)."""
    t = str(exc)
    if "no password supplied" in t:
        return ("Datenbank verlangt ein Passwort, DATABASE_PASSWORD ist leer – "
                "in sens.env eintragen (ohne Anführungszeichen).")
    if "password authentication failed" in t:
        return "Datenbank-Anmeldung fehlgeschlagen – DATABASE_USER/DATABASE_PASSWORD in sens.env prüfen."
    if "does not exist" in t and "database" in t:
        return "Datenbank existiert nicht – wird vom Jenkinsfile (Stufe „Datenbank“) angelegt."
    if "could not translate host name" in t or "Name or service not known" in t:
        return "Datenbank-Host nicht erreichbar – DATABASE_HOST/Docker-Netz prüfen."
    return t.splitlines()[0][:300]
