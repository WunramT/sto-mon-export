"""Lauf anlegen, Auflösung ausführen und speichern (D21, D23)."""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import rules
from .explode import SPALTEN, Aufloeser, Ergebnis, Optionen
from .source import SapSource

log = logging.getLogger(__name__)


def roots_aus_db(eng: Engine) -> tuple[list[str], list[str]]:
    """D22: aktive root_material und root_ausschluss."""
    with eng.connect() as con:
        roots = list(con.execute(sa.text("SELECT matnr FROM basis_bom.root_material WHERE gueltig_bis IS NULL "
                                         "ORDER BY matnr")).scalars())  # fmt: skip
        aus = list(
            con.execute(sa.text("SELECT matnr FROM basis_bom.root_ausschluss ORDER BY matnr")).scalars()
        )
    return roots, aus


def starte_lauf(eng: Engine, src: SapSource, regeln: rules.Regelstand) -> int:
    with eng.begin() as con:
        return con.execute(
            sa.text(
                "INSERT INTO basis_bom.lauf (export_datum, regel_version) VALUES (:e, :r) RETURNING lauf_id"
            ),
            {"e": src.stichtag, "r": regeln.version},
        ).scalar_one()


def beende_lauf(eng: Engine, lauf_id: int, status: str, statistik: dict) -> None:
    with eng.begin() as con:
        con.execute(
            sa.text(
                "UPDATE basis_bom.lauf SET beendet = now(), status = :s, "
                "statistik = statistik || CAST(:st AS jsonb) WHERE lauf_id = :l"
            ),
            {"s": status, "st": json.dumps(statistik, default=str), "l": lauf_id},
        )


def lauf_status(eng: Engine, lauf_id: int) -> str:
    with eng.connect() as con:
        return con.execute(
            sa.text("SELECT status FROM basis_bom.lauf WHERE lauf_id = :l"), {"l": lauf_id}
        ).scalar()


def speichere(eng: Engine, lauf_id: int, erg: Ergebnis) -> None:
    """COPY nach basis_bom.aufloesung und basis_bom.ebene_marker."""
    raw = eng.raw_connection()
    try:
        with raw.cursor() as cur:
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            for z in erg.zeilen:
                w.writerow([lauf_id] + [_wert(z[c], c) for c in SPALTEN])
            buf.seek(0)
            cols = ", ".join(["lauf_id", *SPALTEN])
            with cur.copy(
                f"COPY basis_bom.aufloesung ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
            ) as cp:
                cp.write(buf.getvalue())
            for m in erg.ebene_marker:
                cur.execute(
                    "INSERT INTO basis_bom.ebene_marker (lauf_id, root_matnr, stlnr, marker, merkmal) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (lauf_id, m["root_matnr"], m["stlnr"], m["marker"], m["merkmal"] or None),
                )
        raw.commit()
    finally:
        raw.close()


def _wert(v, col: str):
    if col == "spur":
        return json.dumps(v, ensure_ascii=False, default=str)
    return "\\N" if v is None else v


def fuehre_aufloesung_aus(
    eng: Engine, matnr: Iterable[str] | None = None, optionen: Optionen | None = None
) -> tuple[int, Ergebnis]:
    """Auflösung für alle Root-Materialien oder die angegebenen; speichert Lauf und Ergebnis."""
    src = SapSource.from_db(eng)
    regeln = rules.lade_regelstand(eng)
    lauf_id = starte_lauf(eng, src, regeln)
    try:
        roots, aus = roots_aus_db(eng)
        if matnr:
            gewuenscht = [m.strip().lstrip("0") for m in matnr]
            unbekannt = sorted(set(gewuenscht) - set(roots))
            if unbekannt:
                log.warning("nicht in root_material (trotzdem aufgelöst): %s", unbekannt)
            roots = gewuenscht
        aufl = Aufloeser(src, regeln, optionen)
        erg = aufl.loese_alle(roots, aus)
        speichere(eng, lauf_id, erg)
        # D7/D8: neue Werte und Kürzel landen als OFFEN – nach dem Lesen des Regelstands (regel_version bleibt)
        rules.trage_offen_ein(eng, erg.neue_paare, f"lauf:{lauf_id}")
        rules.trage_alias_offen_ein(eng, erg.neue_aliasse, f"lauf:{lauf_id}")
        beende_lauf(eng, lauf_id, "aufgeloest", {"aufloesung": erg.statistik(), "stichtag": src.stichtag,
                                                "export_daten": src.export_daten})  # fmt: skip
    except Exception as exc:
        beende_lauf(eng, lauf_id, "fehler", {"fehler": repr(exc)})
        raise
    return lauf_id, erg
