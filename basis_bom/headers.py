"""Header-Mapping beschreibend → technisch für SE16-/SQL-Exporte (docs/EXPORTE.md).

Schlüssel werden vor dem Vergleich normalisiert (`normalisiere_header`: Großschrift, Umlaute ausgeschrieben,
Satzzeichen weg). Technische Namen (`MATNR`, …) passen immer. Einträge mit `# vermutet` sind aus den
SAP-Feldbezeichnern abgeleitet und beim ersten Laden gegen die echten Header zu prüfen; unbekannte Spalten
protokolliert der Loader und lädt sie unter normalisiertem Namen mit.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

# Pro Tabelle die technischen Spalten, die EXPORT-PLAN Phase 2/3 nennt.
SPALTEN: dict[str, list[str]] = {
    "MAST": ["MATNR", "WERKS", "STLAN", "STLNR", "STLAL", "DATUV", "AENNR", "LKENZ"],
    "STPO": [
        "STLTY",
        "STLNR",
        "STLKN",
        "STPOZ",
        "POSNR",
        "IDNRK",
        "POSTP",
        "MENGE",
        "MEINS",
        "KNOBJ",
        "ALPGR",
        "ALPRF",
        "DATUV",
        "AENNR",
        "LKENZ",
    ],
    "STAS": ["STLTY", "STLNR", "STLAL", "STLKN", "STASZ", "DATUV", "AENNR", "LKENZ"],
    "STKO": [
        "STLTY",
        "STLNR",
        "STLAL",
        "STKOZ",
        "BMENG",
        "BMEIN",
        "STLST",
        "DATUV",
        "AENNR",
        "LOEKZ",
        "LKENZ",
    ],
    "CUOB": ["KNTAB", "KNOBJ", "KNNUM", "KNSRT", "DATUV", "AENNR", "LKENZ"],
    "CUKB": ["KNNUM", "ADZHL", "KNNAM", "KNART", "KNSTA", "DATUV", "AENNR", "LKENZ"],
    "CUKBT": ["KNNUM", "SPRAS", "ADZHL", "KNKTX", "DATUV", "AENNR", "LKENZ"],
    "MARA": ["MATNR", "MATKL", "MTART", "KZKFG"],
    "MARC": ["MATNR", "WERKS", "DISPO", "SOBSL", "BESKZ"],
    "MAKT": ["MATNR", "SPRAS", "MAKTX"],
    "CABN": ["ATINN", "ATNAM", "ATFOR", "ATEIN", "ATSON", "DATUV", "AENNR", "LKENZ"],
    "CAWN": ["ATINN", "ATZHL", "ATWRT", "ATFLV", "ATFLB", "ATCOD", "DATUV", "AENNR", "LKENZ"],
    "CAWNT": ["ATINN", "ATZHL", "SPRAS", "ATWTB"],
}

# Gilt für alle Tabellen, sofern die Tabelle keinen eigenen Eintrag hat.
ALLGEMEIN: dict[str, str] = {
    "MATERIAL": "MATNR",
    "MATERIALNUMMER": "MATNR",
    "WERK": "WERKS",
    "STUECKLISTENVERWENDUNG": "STLAN",  # vermutet
    "VERWENDUNG": "STLAN",  # vermutet
    "STUECKLVERWENDUNG": "STLAN",  # belegt: EXPORT_mast_20260923 „StücklVerwendung“
    "STUECKLALTERNATIVE": "STLAL",  # belegt: EXPORT_mast_20260923 „StücklAlternative“
    "STUECKLISTENVERW": "STLAN",  # vermutet
    "STUELIVERWENDUNG": "STLAN",  # vermutet
    "STLVERWENDUNG": "STLAN",  # vermutet
    "VERW": "STLAN",  # vermutet
    "STUECKLISTE": "STLNR",  # vermutet
    "ALTERNATIVE STUECKLISTE": "STLAL",  # vermutet
    "ALTERNATIVSTUECKLISTE": "STLAL",  # vermutet
    "ALTERNATIVE": "STLAL",  # vermutet
    "ALT STUECKLISTE": "STLAL",  # vermutet
    "ALTSTUECKLISTE": "STLAL",  # vermutet
    "ALTERNATIV STUECKLISTE": "STLAL",  # vermutet
    "STUECKLISTENTYP": "STLTY",  # vermutet
    "KNOTEN": "STLKN",  # vermutet
    "KNOTENNUMMER": "STLKN",  # vermutet
    "POSITIONSKNOTENNUMMER": "STLKN",  # vermutet
    "POSITIONSKNOTEN": "STLKN",  # vermutet
    "KNOTEN STUECKLISTENPOSITION": "STLKN",  # vermutet
    "POSITIONSKNOTEN NR": "STLKN",  # vermutet
    "GUELTIG AB": "DATUV",
    "AENDERUNGSNUMMER": "AENNR",
    "LOESCHKENNZEICHEN": "LKENZ",
    "LOESCHVERMERK": "LKENZ",  # vermutet
    "SPRACHE": "SPRAS",  # vermutet
    "SPRACHENSCHLUESSEL": "SPRAS",  # vermutet
    # CUOB / CUKB (aus legacy/basis_bom_v0.py belegt)
    "ZUORDNUNGSNUMMER": "KNOBJ",
    "INTERNE NUMMER DES WISSENSBAUSTEINS": "KNNUM",
    "BEZIEHUNG": "KNNAM",
    "TABELLE": "KNTAB",  # vermutet
    "ART DES BEZIEHUNGSWISSENS": "KNART",  # vermutet (docs/EXPORTE.md Prüfpunkt 1)
    "BEZIEHUNGSART": "KNART",  # vermutet
    "STATUS DES BEZIEHUNGSWISSENS": "KNSTA",  # vermutet
    "STATUS BEZIEHUNGSWISSEN": "KNSTA",  # vermutet
    "BEZEICHNUNG BEZIEHUNGSWISSEN": "KNKTX",  # vermutet
    # STPO
    "POSITIONSNUMMER": "POSNR",  # vermutet
    "POSITION": "POSNR",  # vermutet
    "KOMPONENTE": "IDNRK",  # vermutet
    "STUECKLISTENKOMPONENTE": "IDNRK",  # vermutet
    "POSITIONSTYP": "POSTP",  # vermutet
    "KOMPONENTENMENGE": "MENGE",  # vermutet
    "MENGE": "MENGE",
    "KOMPONENTENMENGENEINHEIT": "MEINS",  # vermutet
    "MENGENEINHEIT": "MEINS",  # vermutet
    "OBJEKTABHAENGIGKEIT": "KNOBJ",  # vermutet
    "ALTERNATIVPOSITIONSGRUPPE": "ALPGR",  # vermutet
    "ALTERNATIVPOSITION GRUPPE": "ALPGR",  # vermutet
    "RANGFOLGE": "ALPRF",  # vermutet
    "RANGFOLGE ALTERNATIVPOSITION": "ALPRF",  # vermutet
    # STKO
    "BASISMENGE": "BMENG",  # vermutet
    "BASISMENGENEINHEIT": "BMEIN",  # vermutet
    "STUECKLISTENSTATUS": "STLST",  # vermutet
    "LOESCHVORMERKUNG": "LOEKZ",  # vermutet
    # MARA / MARC / MAKT
    "WARENGRUPPE": "MATKL",
    "MATERIALART": "MTART",
    "KONFIGURIERBARES MATERIAL": "KZKFG",  # vermutet
    "MATERIAL IST KONFIGURIERBAR": "KZKFG",  # vermutet
    "DISPONENT": "DISPO",
    "SONDERBESCHAFFUNGSART": "SOBSL",  # vermutet
    "SONDERBESCHAFFUNG": "SOBSL",  # vermutet
    "BESCHAFFUNGSART": "BESKZ",  # vermutet
    "MATERIALKURZTEXT": "MAKTX",
    "KURZTEXT": "MAKTX",  # vermutet
    # CABN / CAWN
    "INTERNES MERKMAL": "ATINN",  # vermutet
    "MERKMALNAME": "ATNAM",  # vermutet
    "MERKMAL": "ATNAM",  # vermutet
    "DATENTYP": "ATFOR",  # vermutet
    "EINWERTIG": "ATEIN",  # vermutet
    "MERKMALWERT": "ATWRT",  # vermutet
    "MERKMALWERT BEZEICHNUNG": "ATWTB",  # vermutet
}

# Mehrdeutige Bezeichner (z. B. „Interner Zähler“ ist je Tabelle ein anderes Feld).
PRO_TABELLE: dict[str, dict[str, str]] = {
    "STPO": {"INTERNER ZAEHLER": "STPOZ", "ZAEHLER": "STPOZ"},  # vermutet
    "STAS": {"KNOTEN POSITION": "STLKN", "INTERNER ZAEHLER": "STASZ", "ZAEHLER": "STASZ"},  # vermutet
    "STKO": {
        "INTERNER ZAEHLER": "STKOZ",
        "ZAEHLER": "STKOZ",
        "LOESCHKENNZEICHEN STUECKLISTE": "LOEKZ",
    },  # vermutet
    "CUOB": {
        "TABELLEN ID": "KNTAB",
        "ZAEHLER F SORTIERUNG": "KNSRT",
        "SORTIERUNG": "KNSRT",
        "INT ZAEHLER": "ADZHL",
    },  # belegt: EXPORT_20260512_153230_cuob
    "CUKB": {
        "INT ZAEHLER": "ADZHL",
        "INTERNER ZAEHLER": "ADZHL",
        "ZAEHLER": "ADZHL",
        "STATUS": "KNSTA",
    },  # vermutet
    "CUKBT": {
        "INT ZAEHLER": "ADZHL",
        "INTERNER ZAEHLER": "ADZHL",
        "ZAEHLER": "ADZHL",
        "BEZEICHNUNG": "KNKTX",
    },  # vermutet
    "CABN": {
        "INT MERKMALSNUMMER": "ATINN",
        "INT MERKMALNUMMER": "ATINN",
        "INTERNE MERKMALSNUMMER": "ATINN",
        "INT ZAEHLER": "ADZHL",
        "INTERNER ZAEHLER": "ADZHL",
    },  # belegt durch EXPORT_cabn_20260923 (ATINN)
    "CAWN": {
        "INTERNER ZAEHLER": "ATZHL",
        "ZAEHLER": "ATZHL",
        "INT MERKMALSNUMMER": "ATINN",
        "INT MERKMALNUMMER": "ATINN",
    },  # vermutet
    "CAWNT": {
        "INTERNER ZAEHLER": "ATZHL",
        "ZAEHLER": "ATZHL",
        "INT MERKMALSNUMMER": "ATINN",
        "INT MERKMALNUMMER": "ATINN",
    },  # vermutet
}

_UMLAUTE = str.maketrans({"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"})


def normalisiere_header(h: object) -> str:
    s = str(h).strip().upper().translate(_UMLAUTE)
    s = re.sub(r"[^A-Z0-9_]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


OVERRIDE_DATEI = Path(__file__).resolve().parent.parent / "docs" / "header_mapping.csv"


@lru_cache(maxsize=1)
def _override() -> dict[tuple[str, str], str]:
    """Lokale Zuordnungen aus docs/header_mapping.csv (`tabelle;header;technisch`, `*` = alle Tabellen).
    Hat Vorrang vor den eingebauten Tabellen; so lassen sich echte Export-Header ohne Codeänderung zuordnen."""
    if not OVERRIDE_DATEI.exists():
        return {}
    out = {}
    with OVERRIDE_DATEI.open(encoding="utf-8-sig") as f:
        for zeile in csv.reader(f, delimiter=";"):
            if len(zeile) < 3 or zeile[0].strip().startswith("#") or zeile[0].strip().lower() == "tabelle":
                continue
            out[(zeile[0].strip().upper(), _kompakt(normalisiere_header(zeile[1])))] = (
                zeile[2].strip().upper()
            )
    return out


def _kompakt(n: str) -> str:
    return n.replace(" ", "")


def technischer_name(tabelle: str, header: object) -> str | None:
    """Technischer Feldname oder None, wenn der Header unbekannt ist."""
    n = normalisiere_header(header)
    k = _kompakt(n)
    tab = tabelle.upper()
    ov = _override()
    if (tab, k) in ov or ("*", k) in ov:
        return ov.get((tab, k)) or ov[("*", k)]
    tech = {c for cols in SPALTEN.values() for c in cols}
    if n.replace(" ", "_") in tech:
        return n.replace(" ", "_")
    spezifisch = {_kompakt(h): t for h, t in PRO_TABELLE.get(tab, {}).items()}
    if k in spezifisch:
        return spezifisch[k]
    return {_kompakt(h): t for h, t in ALLGEMEIN.items()}.get(k)


def ersatzname(header: object) -> str:
    """Spaltenname für unbekannte Header (bleiben erhalten, D-unabhängig)."""
    return normalisiere_header(header).replace(" ", "_") or "SPALTE"
