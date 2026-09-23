"""Lesbare Darstellung von Auflösung und Spur (Notebooks 30/90, Review-Blatt)."""

from __future__ import annotations

import pandas as pd

from .explode import AUSGESCHLOSSEN, AUSGESCHLOSSEN_VERERBT, IGNORIERT

SYMBOL = {
    "basis": "✔", "unbedingt": "●", "ausgeschlossen": "✘", "ausgeschlossen_vererbt": "✘", "manuell_prüfen": "?",
    "unterhalb_manuell": "?", "ignoriert": "·",
}  # fmt: skip
EINGEKLAPPT = {AUSGESCHLOSSEN, AUSGESCHLOSSEN_VERERBT, IGNORIERT}


def spur_lesbar(spur: dict) -> str:
    """Spur (D18) als kurzer Text: Beziehungen, Prüfungen, gewählte Rangwerte."""
    teile = []
    for b in spur.get("beziehungen", []):
        if b.get("rolle") != "auswahl":
            teile.append(f"{b['knnam']} [{b.get('rolle')}]")
            continue
        pr = ", ".join(f"{p['merkmal']}={p['wert']} {p['ergebnis']}" for p in b.get("pruefungen", []))
        teile.append(f"{b['knnam']} → {pr or b.get('fehler') or 'keine Paare'}")
    for p in spur.get("prozeduren", []):
        teile.append(f"Prozedur {p} ignoriert")
    gew = spur.get("gewaehlt") or {}
    if gew:
        teile.append("gewählt: " + ", ".join(f"{m}={w or '–'}" for m, w in gew.items()))
    return " | ".join(teile)


def baum_text(df: pd.DataFrame, eingeklappt: bool = True, kurztext: dict | None = None) -> str:
    """Baum in Pfad-Reihenfolge. Ausgeschlossene Zweige eingeklappt: nur die oberste Zeile, mit Zähler."""
    kurztext = kurztext or {}
    d = df.sort_values("pfad", key=lambda s: s.str.split("/").map(lambda x: [p.split(":")[0] for p in x]))
    zeilen, zu = [], None
    for _, z in d.iterrows():
        if eingeklappt and zu is not None and z["pfad"].startswith(zu + "/"):
            continue
        n = ""
        if eingeklappt and z["status"] in EINGEKLAPPT:
            unter = int(d["pfad"].str.startswith(z["pfad"] + "/").sum())
            n = f"  (+{unter} eingeklappt)" if unter else ""
            zu = z["pfad"]
        else:
            zu = None
        text = kurztext.get(z["matnr"], "")
        menge = "" if pd.isna(z["menge_kum"]) else f"{z['menge_kum']:g} {z['meins']}"
        zeilen.append(
            f"{'  ' * (z['ebene'] - 1)}{SYMBOL.get(z['status'], ' ')} {z['posnr']} {z['matnr'] or '(ohne Material)'} "
            f"{text} {menge} [{z['status']}] {z['grund']}{n}".rstrip()
        )
    return "\n".join(zeilen)
