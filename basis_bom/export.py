"""SAP-Format-Export (D19), exakt wie `export_grundversion_sap_format` im Legacy-Skript.

Spalten: Werk | Material | ObjektId | Materialkurztext DE | Menge | ME | PTp | Disp. | Warengrp (+ MArt, SoB,
sofern MARA/MARC exportiert). Erste Zeile pro Root-Material = Kopfzeile ohne ObjektId/Menge. Nur Positionen mit
Status `basis`/`unbedingt`. Menge = Positionsmenge wie im Legacy-Skript (docs/FRAGEN.md Q29), Dezimalkomma.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config
from .explode import EXPORT_STATUS
from .source import SapSource

GRUNDSPALTEN = [
    "Werk",
    "Material",
    "ObjektId",
    "Materialkurztext DE",
    "Menge",
    "ME",
    "PTp",
    "Disp.",
    "Warengrp",
]
MENGE_SPALTE = "menge"


def _menge(v) -> str:
    try:
        return str(float(v)).replace(".", ",")
    except (TypeError, ValueError):
        return "" if v is None else str(v)


def sap_format(aufloesung: pd.DataFrame, src: SapSource, werks: str = config.WERKS) -> pd.DataFrame:
    maktx = src.lookup("MAKT", "MAKTX")
    dispo = src.lookup("MARC", "DISPO")
    matkl = src.lookup("MARA", "MATKL")
    mtart = src.lookup("MARA", "MTART")
    sobsl = src.lookup("MARC", "SOBSL")
    mit_mart = src.mara is not None and "MTART" in src.mara.columns
    mit_sob = src.marc is not None and "SOBSL" in src.marc.columns
    spalten = GRUNDSPALTEN + (["MArt"] if mit_mart else []) + (["SoB"] if mit_sob else [])

    def zusatz(m: str) -> dict:
        z = {}
        if mit_mart:
            z["MArt"] = mtart.get(m, "")
        if mit_sob:
            z["SoB"] = sobsl.get(m, "")
        return z

    rows: list[dict] = []
    basis = aufloesung[aufloesung["status"].isin(EXPORT_STATUS)]
    basis = basis.sort_values(["root_matnr", "lfd"]).sort_values(
        ["root_matnr", "ebene", "parent_matnr"], kind="stable"
    )
    for root in dict.fromkeys(aufloesung.sort_values("root_matnr")["root_matnr"]):
        rows.append({"Werk": werks, "Material": root, "ObjektId": "", "Materialkurztext DE": maktx.get(root, ""),
                     "Menge": "", "ME": "", "PTp": "", "Disp.": dispo.get(root, ""), "Warengrp": matkl.get(root, ""),
                     **zusatz(root)})  # fmt: skip
        for z in basis[basis["root_matnr"] == root].itertuples():
            m = z.matnr
            rows.append({"Werk": werks, "Material": root, "ObjektId": m, "Materialkurztext DE": maktx.get(m, ""),
                         "Menge": _menge(getattr(z, MENGE_SPALTE)), "ME": z.meins, "PTp": z.postp,
                         "Disp.": dispo.get(m, ""), "Warengrp": matkl.get(m, ""), **zusatz(m)})  # fmt: skip
    return pd.DataFrame(rows, columns=spalten)


def schreibe(df: pd.DataFrame, pfad: Path) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(pfad, index=False, sep=";", lineterminator="\n", encoding="utf-8")
    return pfad


def exportiere(aufloesung: pd.DataFrame, src: SapSource, ziel: Path) -> list[Path]:
    """Eine Datei pro Root-Material plus Gesamtdatei `grundversion_sap_format.csv`."""
    gesamt = sap_format(aufloesung, src)
    pfade = [schreibe(gesamt, ziel / "grundversion_sap_format.csv")]
    for root, teil in gesamt.groupby("Material", sort=True):
        pfade.append(schreibe(teil, ziel / str(root) / f"{root}_sap_format.csv"))
    return pfade
