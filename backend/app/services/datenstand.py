"""Datenstand: Schema anlegen, SAP-Exporte (vom Host gemountet) im Hintergrund laden, Status für die Oberfläche.

Der Ladevorgang dauert mit echten Exporten (STPO ~1 GB) mehrere Minuten. Das Backend meldet sich trotzdem sofort
gesund; die fachlichen Endpunkte antworten bis zum Ende mit 503 und die Oberfläche zeigt den Fortschritt.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import Engine

from basis_bom import db, loader, pruefpunkte, rules
from basis_bom.dienst import Dienst

log = logging.getLogger(__name__)

LEER, LAEDT, BEREIT, FEHLER = "leer", "laedt", "bereit", "fehler"


@dataclass
class Status:
    zustand: str = LEER
    schritt: str | None = None
    quelle: str | None = None  # "exporte" | "beispieldaten" | "datenbank"
    gestartet: str | None = None
    beendet: str | None = None
    dauer_s: float | None = None
    fehler: str | None = None
    meldung: str | None = None
    schritte: list[str] = field(default_factory=list)


class Datenstand:
    def __init__(self, eng: Engine, exports_dir: Path, out_dir: Path, demo_fixtures: bool = False) -> None:
        self.eng = eng
        self.exports_dir = exports_dir
        self.out_dir = out_dir
        self.demo_fixtures = demo_fixtures
        self.dienst = Dienst(eng)
        self._status = Status()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------------------------------------------------
    @property
    def status(self) -> Status:
        return self._status

    @property
    def bereit(self) -> bool:
        return self._status.zustand == BEREIT

    def exportdateien(self) -> list[dict]:
        if not self.exports_dir.is_dir():
            return []
        out = []
        for p in sorted(self.exports_dir.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                st = p.stat()
                geaendert = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
                out.append({"name": p.name, "groesse": st.st_size, "geaendert": geaendert})
        return out

    def info(self) -> dict:
        d = asdict(self._status)
        d["exports_dir"] = str(self.exports_dir)
        d["dateien"] = self.exportdateien()
        if self.bereit:
            try:
                s = self.dienst.src
                d["stichtag"] = str(s.stichtag)
                d["warnungen"] = list(s.warnungen)
            except Exception:  # pragma: no cover - nur Anzeige
                log.warning("Stichtag nicht lesbar", exc_info=True)
        return d

    # ------------------------------------------------------------------------------------------------------------
    def beim_start(self) -> None:
        """Schema idempotent anlegen; ist sap_raw leer, im Hintergrund laden (Exporte, sonst ggf. Beispieldaten)."""
        db.init_schema(self.eng)
        db.init_views(self.eng)
        if db.table_exists(self.eng, "sap_raw", "mast"):
            # Nach jedem Neustart: SAP-Daten aus der Datenbank lesen und vorberechnen. Solange heißt es „laedt“ –
            # sonst warten alle Anfragen (auch /datenstand) ohne Rückmeldung auf die Vorberechnung.
            t0 = time.monotonic()
            jetzt = datetime.now().isoformat(timespec="seconds")
            self._status = Status(zustand=LAEDT, quelle="datenbank", gestartet=jetzt)
            self._vorwaermen()
            self._schritt_ende()
            self._status.zustand = BEREIT
            self._status.schritt = None
            self._status.meldung = "Daten aus der Datenbank"
            self._status.beendet = datetime.now().isoformat(timespec="seconds")
            self._status.dauer_s = round(time.monotonic() - t0, 1)
            log.info("Datenstand: bereit nach %.1f s", self._status.dauer_s)
            return
        if self.exportdateien():
            self.starte("exporte")
        elif self.demo_fixtures:
            self.starte("beispieldaten")
        else:
            self._status = Status(zustand=LEER, meldung=f"Keine Exporte in {self.exports_dir} gefunden.")

    def starte(self, quelle: str = "exporte") -> bool:
        """Startet den Ladevorgang im Hintergrund. False, wenn schon einer läuft."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            if quelle == "exporte" and not self.exportdateien():
                raise FileNotFoundError(f"Keine Exporte in {self.exports_dir} gefunden.")
            jetzt = datetime.now().isoformat(timespec="seconds")
            self._status = Status(zustand=LAEDT, quelle=quelle, gestartet=jetzt)
            self._thread = threading.Thread(target=self._lade, args=(quelle,), name="datenstand", daemon=True)
            self._thread.start()
            return True

    def warte(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ------------------------------------------------------------------------------------------------------------
    def _schritt(self, text: str) -> None:
        self._schritt_ende()
        log.info("Datenstand: %s", text)
        self._status.schritt = text
        self._status.schritte.append(text)
        self._schritt_t0 = time.monotonic()

    def _schritt_ende(self) -> None:
        """Dauer des vorigen Schritts ins Log (zeigt bei echten Daten, was lange dauert)."""
        t0 = self.__dict__.pop("_schritt_t0", None)
        if t0 is not None and self._status.schritt:
            log.info("Datenstand: %s – fertig nach %.1f s", self._status.schritt, time.monotonic() - t0)

    def _lade(self, quelle: str) -> None:
        t0 = time.monotonic()
        try:
            self._schritt("Datenbank vorbereiten")
            db.init_schema(self.eng)
            if quelle == "beispieldaten":
                self._schritt("Beispieldaten lesen")
                erg = loader.lade_fixtures()
                self._schritt("In die Datenbank schreiben")
                loader.schreibe(self.eng, erg, quelle_roots="fixtures")
            else:
                self._schritt("SAP-Exporte lesen (STPO kann einige Minuten dauern)")
                erg = loader.lade_verzeichnis(self.exports_dir, db.kanonische_merkmale(self.eng))
                self._schritt("In die Datenbank schreiben")
                loader.schreibe(self.eng, erg, quelle_roots=loader.ROOT_XLSX)
                self.out_dir.mkdir(parents=True, exist_ok=True)
                (self.out_dir / "header_bericht.md").write_text(
                    loader.header_bericht(erg.protokoll.values()), encoding="utf-8"
                )
                pruefpunkte.schreibe_fragen(
                    pruefpunkte.berichte(erg, set(db.kanonische_merkmale(self.eng))), self.out_dir / "FRAGEN.md"
                )
                self._schritt("Kürzel aus CABN übernehmen")
                rules.aliasse_aus_cabn(self.eng)
            self._schritt("Auswertungen anlegen")
            db.init_views(self.eng)
            self.dienst.neu_laden()
            self._vorwaermen()
            self._schritt_ende()
            self._status.zustand = BEREIT
            self._status.schritt = None
            self._status.meldung = "Exporte geladen" if quelle == "exporte" else "Beispieldaten geladen"
        except Exception as exc:  # noqa: BLE001 - Fehler wird in der Oberfläche angezeigt
            log.exception("Laden fehlgeschlagen")
            self._status.zustand = FEHLER
            self._status.fehler = f"{type(exc).__name__}: {exc}"
        finally:
            self._status.beendet = datetime.now().isoformat(timespec="seconds")
            self._status.dauer_s = round(time.monotonic() - t0, 1)

    def _vorwaermen(self) -> None:
        try:
            self._schritt("SAP-Daten aus der Datenbank lesen")
            _ = self.dienst.src
            self._schritt("Stücklisten auswerten")
            self.dienst.meta()
            self._schritt("Materialliste vorbereiten")
            self.dienst.materialien()
        except Exception:  # pragma: no cover - leere/inkonsistente DB zeigt sich später mit Fehlermeldung
            log.exception("Vorberechnung fehlgeschlagen")
