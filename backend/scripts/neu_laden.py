"""Exporte neu laden lassen (für Jenkins: `docker exec <backend> python scripts/neu_laden.py`).

Meldet sich mit dem Passwort aus der Umgebung am laufenden Backend an und startet den Ladevorgang; wartet optional
bis zum Ende (--warten) und endet mit Fehlercode, wenn das Laden fehlschlägt.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASIS = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000/api")


def aufruf(methode: str, pfad: str, daten: dict | None = None, token: str | None = None) -> dict:
    req = urllib.request.Request(BASIS + pfad,  # noqa: S310 - feste http-URL aus der Umgebung method=methode, data=json.dumps(daten or {}).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.load(r)
    except urllib.error.HTTPError as exc:
        sys.exit(f"{methode} {pfad}: {exc.code} {exc.read().decode(errors='replace')}")


def main() -> None:
    token = aufruf("POST", "/auth/login", {"passwort": os.environ.get("MASTER_PASSWORD_ADMIN", "")})["access_token"]
    info = aufruf("POST", "/datenstand/neu-laden", token=token)
    print(f"Ladevorgang gestartet: {len(info['dateien'])} Dateien in {info['exports_dir']}")
    if "--warten" not in sys.argv:
        return
    while True:
        time.sleep(10)
        info = aufruf("GET", "/datenstand", token=token)
        print(f"  {info['zustand']}: {info.get('schritt') or info.get('meldung') or ''}", flush=True)
        if info["zustand"] == "bereit":
            print(f"Fertig in {info['dauer_s']} s, Stichtag {info.get('stichtag')}")
            return
        if info["zustand"] == "fehler":
            sys.exit(f"Laden fehlgeschlagen: {info['fehler']}")


if __name__ == "__main__":
    main()
