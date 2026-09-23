"""Konsistenz- und Exportprüfungen aus sql/checks (D23: erster Schritt des Laufs)."""

from __future__ import annotations

import logging

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

from . import db

log = logging.getLogger(__name__)


def pruefe(eng: Engine) -> pd.DataFrame:
    """Alle Prüfungen; fehlt eine Tabelle, wird die Prüfung als übersprungen (ok = None) gemeldet."""
    zeilen = []
    for pfad in db.sql_files("checks"):
        sql = pfad.read_text(encoding="utf-8")
        try:
            with eng.connect() as con:
                for r in con.execute(sa.text(sql)).mappings():
                    zeilen.append({"datei": pfad.name, **r})
        except ProgrammingError as exc:
            grund = str(exc.orig).splitlines()[0] if exc.orig else str(exc)
            zeilen.append(
                {"datei": pfad.name, "pruefung": pfad.stem, "ok": None, "detail": f"übersprungen: {grund}"}
            )
    return pd.DataFrame(zeilen, columns=["datei", "pruefung", "ok", "detail"])
