"""Lesbare Darstellung von Auflösung und Spur (Notebooks 30/90, Review-Blatt)."""

from __future__ import annotations

import pandas as pd

from .explode import AUSGESCHLOSSEN, AUSGESCHLOSSEN_VERERBT, IGNORIERT

SYMBOL = {
    "basis": "✔", "unbedingt": "●", "ausgeschlossen": "✘", "ausgeschlossen_vererbt": "✘", "manuell_prüfen": "?",
    "unterhalb_manuell": "?", "ignoriert": "·",
}  # fmt: skip
EINGEKLAPPT = {AUSGESCHLOSSEN, AUSGESCHLOSSEN_VERERBT, IGNORIERT}


def pfad_sortierung(pfad: str) -> str:
    """Sortierschlüssel für Baumreihenfolge: Positionsnummern je Ebene aufgefüllt."""
    return "/".join(seg.split(":")[0].zfill(8) for seg in pfad.split("/")[1:])


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
    d = df.assign(_s=df["pfad"].map(pfad_sortierung)).sort_values("_s", kind="stable")
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


def baum_html(df: pd.DataFrame, kurztext: dict | None = None) -> str:
    """Baum als verschachtelte <details>: ausgeschlossene Zweige zugeklappt, sonst offen (Notebook 90)."""
    from html import escape

    kurztext = kurztext or {}
    d = df.assign(_s=df["pfad"].map(pfad_sortierung)).sort_values("_s", kind="stable")
    kinder: dict[str, list] = {}
    for _, z in d.iterrows():
        kinder.setdefault(z["pfad"].rsplit("/", 1)[0], []).append(z)
    farbe = {"basis": "#1a7f37", "unbedingt": "#1a7f37", "manuell_prüfen": "#9a6700",
             "unterhalb_manuell": "#9a6700"}  # fmt: skip

    def knoten(z) -> str:
        menge = "" if pd.isna(z["menge_kum"]) else f"{z['menge_kum']:g} {escape(str(z['meins']))}"
        zeile = (f"<span style='color:{farbe.get(z['status'], '#888')}'>{SYMBOL.get(z['status'], '')} "
                 f"<b>{escape(str(z['posnr']))} {escape(str(z['matnr']) or '(ohne Material)')}</b> "
                 f"{escape(kurztext.get(z['matnr'], ''))} {menge} [{escape(z['status'])}]</span> "
                 f"<small>{escape(str(z['grund'] or ''))}</small>")  # fmt: skip
        unter = kinder.get(z["pfad"], [])
        if not unter:
            return f"<div style='margin-left:1.2em'>{zeile}</div>"
        offen = "" if z["status"] in EINGEKLAPPT else " open"
        inhalt = "".join(knoten(k) for k in unter)
        return f"<details{offen} style='margin-left:1.2em'><summary>{zeile} ({len(unter)})</summary>{inhalt}</details>"

    wurzeln = [p for p in kinder if "/" not in p]
    return "".join(knoten(z) for w in wurzeln for z in kinder[w])
