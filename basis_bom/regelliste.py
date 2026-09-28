"""Regel-Arbeitsliste (XLSX) für den Fachbereich: Regeln und Kürzel ansehen, entscheiden, zurückspielen.

Die Regeln wachsen Beispiel für Beispiel (D24). Die Datei zeigt den aktuellen Regelstand mit den Vorkommen im
letzten Lauf – OFFEN-Werte, die tatsächlich vorkommen, stehen oben. Entschieden wird in den Spalten „Neuer Status“
und „Neuer Rang“; `basis-bom regel import` prüft alles vorab (Ränge eindeutig, D1) und schreibt es historisiert
(D21) in einer Transaktion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.engine import Engine

from .rules import BASIS, NICHT_BASIS, OFFEN, lade_regelstand

STATUS = (BASIS, NICHT_BASIS, OFFEN)
REGELN, KUERZEL = "Regeln", "Kürzel"
R_SPALTEN = ["Merkmal", "Wert", "Status", "Rang", "Begründung", "Positionen", "Stücklisten", "Root-Materialien",
             "Beispiel", "Neuer Status", "Neuer Rang", "Begründung (neu)"]  # fmt: skip
K_SPALTEN = ["Kürzel", "Merkmal", "Status", "Vorkommen", "Beispiel", "Neues Merkmal", "Neuer Status"]
EINGABE = PatternFill("solid", fgColor="FFF2CC")

_VORKOMMEN = """
WITH l AS (SELECT lauf_id FROM basis_bom.letzter_lauf),
p AS (
    SELECT a.root_matnr, a.stlnr, b ->> 'knnam' AS knnam, e ->> 0 AS merkmal,
           regexp_replace(w, '^≠', '') AS wert
    FROM basis_bom.aufloesung a
    JOIN l USING (lauf_id)
    CROSS JOIN LATERAL jsonb_array_elements(a.spur -> 'beziehungen') AS b
    CROSS JOIN LATERAL jsonb_array_elements(coalesce(b -> 'paare', '[]')) AS e
    CROSS JOIN LATERAL regexp_split_to_table(regexp_replace(e ->> 1, '^≠', ''), '[/+]') AS w
)
SELECT merkmal, wert, count(*) AS positionen, count(DISTINCT stlnr) AS stuecklisten,
       count(DISTINCT root_matnr) AS roots, min(knnam) AS beispiel
FROM p GROUP BY merkmal, wert
"""

_KUERZEL_VORKOMMEN = """
WITH l AS (SELECT lauf_id FROM basis_bom.letzter_lauf)
SELECT k AS kuerzel, count(*) AS vorkommen, min(b ->> 'knnam') AS beispiel
FROM basis_bom.aufloesung a
JOIN l USING (lauf_id)
CROSS JOIN LATERAL jsonb_array_elements(a.spur -> 'beziehungen') AS b
CROSS JOIN LATERAL jsonb_array_elements_text(
    coalesce(b -> 'unbekannte_aliasse', '[]') || coalesce(b -> 'offene_aliasse', '[]')) AS k
GROUP BY k
"""


def _abfrage(eng: Engine, sql: str) -> pd.DataFrame:
    with eng.connect() as con:
        return pd.DataFrame(con.execute(sa.text(sql)).mappings().all())


def arbeitsliste(eng: Engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Regeln und nicht verwendbare Kürzel mit Vorkommen im letzten Lauf."""
    rs = lade_regelstand(eng)
    vk = _abfrage(eng, _VORKOMMEN)
    vk_map = {(r.merkmal, r.wert): r for r in vk.itertuples()} if not vk.empty else {}
    zeilen = []
    for r in rs.regeln.values():
        v = vk_map.get((r.merkmal, r.wert))
        zeilen.append({
            "Merkmal": r.merkmal, "Wert": r.wert, "Status": r.status, "Rang": r.rang, "Begründung": None,
            "Positionen": int(v.positionen) if v else 0, "Stücklisten": int(v.stuecklisten) if v else 0,
            "Root-Materialien": int(v.roots) if v else 0, "Beispiel": v.beispiel if v else None,
        })  # fmt: skip
    regeln = pd.DataFrame(zeilen, columns=R_SPALTEN[:9])
    with eng.connect() as con:
        begr = dict(
            ((m, w), b)
            for m, w, b in con.execute(
                sa.text("SELECT merkmal, wert, begruendung FROM basis_bom.regel WHERE gueltig_bis IS NULL")
            )
        )
    regeln["Begründung"] = [begr.get((m, w)) for m, w in zip(regeln["Merkmal"], regeln["Wert"], strict=True)]
    # Arbeitsreihenfolge: vorkommende OFFEN-Werte zuerst, dann je Merkmal BASIS nach Rang
    regeln["_offen_vk"] = (regeln["Status"] == OFFEN) & (regeln["Positionen"] > 0)
    regeln["_st"] = regeln["Status"].map({BASIS: 0, NICHT_BASIS: 1, OFFEN: 2})
    regeln = regeln.sort_values(["_offen_vk", "Positionen", "Merkmal", "_st", "Rang", "Wert"],
                                ascending=[False, False, True, True, True, True]).drop(columns=["_offen_vk", "_st"])  # fmt: skip

    kv = _abfrage(eng, _KUERZEL_VORKOMMEN)
    kv_map = {r.kuerzel: r for r in kv.itertuples()} if not kv.empty else {}
    kz = [
        {
            "Kürzel": a.alias,
            "Merkmal": a.merkmal,
            "Status": a.status,
            "Vorkommen": int(kv_map[a.alias].vorkommen) if a.alias in kv_map else 0,
            "Beispiel": kv_map[a.alias].beispiel if a.alias in kv_map else None,
        }  # fmt: skip
        for a in rs.aliasse.values()
        if a.status != BASIS or not a.merkmal
    ]
    kuerzel = pd.DataFrame(kz, columns=K_SPALTEN[:5]).sort_values(
        ["Vorkommen", "Kürzel"], ascending=[False, True]
    )
    return regeln.reset_index(drop=True), kuerzel.reset_index(drop=True)


def _blatt(ws, df: pd.DataFrame, spalten: list[str], eingabe: list[str], breiten: dict[str, int]) -> None:
    ws.append(spalten)
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row] + [None] * len(eingabe))
    for name in eingabe:
        col = get_column_letter(spalten.index(name) + 1)
        for r in range(2, ws.max_row + 1):
            ws[f"{col}{r}"].fill = EINGABE
    for i, name in enumerate(spalten, start=1):
        ws.column_dimensions[get_column_letter(i)].width = breiten.get(name, 14)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(spalten))}{max(ws.max_row, 2)}"


def exportiere(eng: Engine, ziel: Path) -> Path:
    regeln, kuerzel = arbeitsliste(eng)
    wb = Workbook()
    ws = wb.active
    ws.title = REGELN
    _blatt(ws, regeln, R_SPALTEN, ["Neuer Status", "Neuer Rang", "Begründung (neu)"],
           {"Merkmal": 32, "Wert": 16, "Begründung": 40, "Beispiel": 40, "Begründung (neu)": 40})  # fmt: skip
    status_dv = DataValidation(type="list", formula1='"' + ",".join(STATUS) + '"', allow_blank=True)
    ws.add_data_validation(status_dv)
    col = get_column_letter(R_SPALTEN.index("Neuer Status") + 1)
    status_dv.add(f"{col}2:{col}{ws.max_row + 500}")

    wk = wb.create_sheet(KUERZEL)
    _blatt(wk, kuerzel, K_SPALTEN, ["Neues Merkmal", "Neuer Status"],
           {"Kürzel": 28, "Merkmal": 28, "Beispiel": 40, "Neues Merkmal": 28})  # fmt: skip
    kdv = DataValidation(type="list", formula1='"' + ",".join(STATUS) + '"', allow_blank=True)
    wk.add_data_validation(kdv)
    col = get_column_letter(K_SPALTEN.index("Neuer Status") + 1)
    kdv.add(f"{col}2:{col}{wk.max_row + 500}")

    hi = wb.create_sheet("Hinweise")
    for z in [
        ("Zweck", "Basis-Werte je Merkmal festlegen. Nur die gelben Spalten ausfüllen, dann zurückgeben."),
        (
            "BASIS + Rang",
            "Wert gehört zur Basis. Kommen auf einer Stückliste mehrere BASIS-Werte vor, gewinnt der "
            "kleinste Rang (1 = stärkster). Ränge je Merkmal eindeutig.",
        ),  # fmt: skip
        (
            "NICHT_BASIS",
            "Wert gehört nie zur Basis. Bei Systemregeln (Wert „vorhanden“): Positionen mit dieser "
            "Regel werden ausgeschlossen.",
        ),  # fmt: skip
        ("OFFEN", "Noch nicht entschieden – betroffene Positionen bleiben „manuell prüfen“."),
        ("SITZHOEHE", "Wird automatisch gewählt: der niedrigste vorkommende Wert."),
        (
            "Reihenfolge",
            "Oben stehen OFFEN-Werte, die im letzten Lauf vorkamen (Spalte Positionen) – dort lohnt "
            "die Entscheidung am meisten.",
        ),  # fmt: skip
        (
            "Blatt Kürzel",
            "Kürzel aus Bedingungsnamen, die keinem Merkmal zugeordnet sind. „Neues Merkmal“ = "
            "Merkmalname laut SAP (CABN), „Neuer Status“ = BASIS, wenn die Zuordnung stimmt.",
        ),  # fmt: skip
        (
            "Neue Werte",
            "Tauchen in einem Lauf neue Werte auf, stehen sie beim nächsten Export automatisch als "
            "OFFEN in der Liste.",
        ),  # fmt: skip
    ]:
        hi.append(list(z))
    hi.column_dimensions["A"].width = 18
    hi.column_dimensions["B"].width = 110
    ziel.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ziel)
    return ziel


# -------------------------------------------------------------------------------------------------------------
# Import


@dataclass
class Aenderung:
    merkmal: str
    wert: str
    status: str
    rang: int | None
    begruendung: str | None


@dataclass
class AliasAenderung:
    alias: str
    merkmal: str | None
    status: str


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def lese(datei: Path) -> tuple[list[Aenderung], list[AliasAenderung], list[str]]:
    """Änderungen aus der ausgefüllten Arbeitsliste plus Liste der Eingabefehler."""
    wb = load_workbook(datei, read_only=True, data_only=True)
    fehler: list[str] = []
    regeln: list[Aenderung] = []
    ws = wb[REGELN]
    kopf = list(next(ws.iter_rows(max_row=1, values_only=True)))
    ix = {n: kopf.index(n) for n in R_SPALTEN if n in kopf}
    for nr, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        neu_s, neu_r = _text(r[ix["Neuer Status"]]).upper(), _text(r[ix["Neuer Rang"]])
        if not neu_s and not neu_r:
            continue
        merkmal, wert = _text(r[ix["Merkmal"]]).upper(), _text(r[ix["Wert"]])
        status = neu_s or (BASIS if neu_r else _text(r[ix["Status"]]).upper())
        if status not in STATUS:
            fehler.append(f"Regeln Zeile {nr}: Status {status!r} unbekannt")
            continue
        rang = None
        if neu_r:
            try:
                rang = int(float(neu_r))
            except ValueError:
                fehler.append(f"Regeln Zeile {nr}: Rang {neu_r!r} ist keine Zahl")
                continue
        elif status == BASIS and _text(r[ix["Rang"]]):
            rang = int(float(_text(r[ix["Rang"]])))  # Status bestätigt, alter Rang bleibt
        if status == BASIS and (rang is None or rang < 1):
            fehler.append(f"Regeln Zeile {nr}: {merkmal}={wert} BASIS braucht einen Rang ≥ 1")
            continue
        if status != BASIS:
            rang = None
        regeln.append(Aenderung(merkmal, wert, status, rang, _text(r[ix["Begründung (neu)"]]) or None))
    aliasse: list[AliasAenderung] = []
    if KUERZEL in wb.sheetnames:
        wk = wb[KUERZEL]
        kopf = list(next(wk.iter_rows(max_row=1, values_only=True)))
        ix = {n: kopf.index(n) for n in K_SPALTEN if n in kopf}
        for nr, r in enumerate(wk.iter_rows(min_row=2, values_only=True), start=2):
            neu_m, neu_s = _text(r[ix["Neues Merkmal"]]).upper(), _text(r[ix["Neuer Status"]]).upper()
            if not neu_m and not neu_s:
                continue
            status = neu_s or BASIS
            if status not in STATUS:
                fehler.append(f"Kürzel Zeile {nr}: Status {status!r} unbekannt")
                continue
            if status == BASIS and not neu_m and not _text(r[ix["Merkmal"]]):
                fehler.append(f"Kürzel Zeile {nr}: BASIS braucht ein Merkmal")
                continue
            aliasse.append(AliasAenderung(_text(r[ix["Kürzel"]]).upper(), neu_m or _text(r[ix["Merkmal"]]).upper() or None,
                                          status))  # fmt: skip
    wb.close()
    return regeln, aliasse, fehler


def pruefe_raenge(eng: Engine, aenderungen: list[Aenderung]) -> list[str]:
    """D1: nach Anwendung aller Änderungen ist jeder BASIS-Rang je Merkmal eindeutig."""
    rs = lade_regelstand(eng)
    stand = {(r.merkmal, r.wert): (r.status, r.rang) for r in rs.regeln.values()}
    for a in aenderungen:
        stand[(a.merkmal, a.wert)] = (a.status, a.rang)
    belegt: dict[tuple[str, int], list[str]] = {}
    for (m, w), (s, rang) in stand.items():
        if s == BASIS:
            belegt.setdefault((m, rang), []).append(w)
    return [f"{m}: Rang {rang} doppelt ({', '.join(sorted(ws))})" for (m, rang), ws in sorted(belegt.items())
            if len(ws) > 1]  # fmt: skip


def uebernehme(eng: Engine, regeln: list[Aenderung], aliasse: list[AliasAenderung], von: str) -> None:
    """Alle Änderungen in einer Transaktion: erst alte Zeilen schließen, dann neue einfügen (Rangtausch möglich)."""
    with eng.begin() as con:
        t = con.execute(sa.text("SELECT clock_timestamp()")).scalar()
        for a in regeln:
            con.execute(sa.text("UPDATE basis_bom.regel SET gueltig_bis = :t WHERE merkmal = :m AND wert = :w "
                                "AND gueltig_bis IS NULL"), {"t": t, "m": a.merkmal, "w": a.wert})  # fmt: skip
        for a in regeln:
            con.execute(
                sa.text("INSERT INTO basis_bom.regel (merkmal, wert, status, rang, begruendung, gueltig_von, "
                        "geaendert_von) VALUES (:m, :w, :s, :r, :b, :t, :v)"),
                {"m": a.merkmal, "w": a.wert, "s": a.status, "r": a.rang, "b": a.begruendung, "t": t, "v": von},
            )  # fmt: skip
        for a in aliasse:
            con.execute(sa.text("UPDATE basis_bom.alias SET gueltig_bis = :t WHERE alias = :a AND gueltig_bis IS NULL"),
                        {"t": t, "a": a.alias})  # fmt: skip
            con.execute(
                sa.text("INSERT INTO basis_bom.alias (alias, merkmal, status, gueltig_von, geaendert_von) "
                        "VALUES (:a, :m, :s, :t, :v)"),
                {"a": a.alias, "m": a.merkmal, "s": a.status, "t": t, "v": von},
            )  # fmt: skip
