"""Prüfpunkte 1–8 aus docs/EXPORTE.md beim Laden beantworten und in docs/FRAGEN.md schreiben."""

from __future__ import annotations

import re
from pathlib import Path

from . import config
from .loader import MERKMALLISTE_DEFAULT, Ladeergebnis

START = "<!-- pruefpunkte:start -->"
ENDE = "<!-- pruefpunkte:ende -->"


def _spalten(erg: Ladeergebnis, tab: str, cols: list[str]) -> str:
    p = erg.protokoll.get(tab)
    if p is None:
        return f"{tab}: nicht geladen"
    teile = [f"`{c}` {'ja' if c in p.spalten else '**fehlt**'}" for c in cols]
    return f"{tab}: " + ", ".join(teile)


def berichte(erg: Ladeergebnis, kanonisch: set[str] | None = None) -> str:
    kanonisch = kanonisch or set(MERKMALLISTE_DEFAULT)
    z: list[str] = []
    datei = ", ".join(f"{p.tabelle}={p.datei} ({p.export_datum})" for p in erg.protokoll.values())
    z.append(f"Quelle: {datei}\n")

    z.append("1. **CUKB-Spalten** – " + _spalten(erg, "CUKB", ["KNART", "KNSTA", "DATUV", "ADZHL"]))
    cukb = erg.protokoll.get("CUKB")
    if cukb and "KNART" not in cukb.spalten:
        z.append("   → `KNART` fehlt: Prototyp läuft mit Marker `knart_fehlt` (D10).")
    if cukb and cukb.unbekannte_spalten:
        z.append(f"   Unbekannte Header CUKB: {', '.join(cukb.unbekannte_spalten)}")

    cuob = erg.protokoll.get("CUOB")
    z.append(
        f"2. **CUOB/CUKB auf Werk 4000 gefiltert?** CUOB roh {cuob.zeilen_roh if cuob else '–'} → "
        f"{cuob.zeilen_geladen if cuob else '–'} Zeilen (KNOBJ ∈ K); CUKB roh {cukb.zeilen_roh if cukb else '–'} → "
        f"{cukb.zeilen_geladen if cukb else '–'} (KNNUM ∈ W)."
    )
    if "W" in erg.abgleich:
        a = erg.abgleich["W"]
        z.append(f"   Abgleich W.csv: Datei {a['datei']}, berechnet {a['berechnet']}, nur Datei "
                 f"{a['anzahl_nur_datei']}, nur berechnet {a['anzahl_nur_berechnet']}.")  # fmt: skip

    z.append("3. **Gültigkeitsspalten** – " + "; ".join(
        _spalten(erg, t, ["LKENZ", "DATUV", "AENNR"]) for t in ("MAST", "STPO", "STAS", "STKO")))  # fmt: skip

    stpo = erg.protokoll.get("STPO")
    if stpo:
        z.append(f"4. **STPO roh vs. STLNR ∈ S:** {stpo.zeilen_roh} → {stpo.zeilen_geladen} Zeilen "
                 f"(|S| = {len(erg.schluessel.get('S', ()))}, alle Stücklisten Werk/Verwendung: "
                 f"{len(erg.schluessel.get('S_alle', erg.schluessel.get('S', ())))}).")  # fmt: skip

    ri = erg.root_info
    if ri:
        z.append(
            f"5. **Planzeiten-XLSX:** Blätter {ri.get('blaetter')}; Materialnummern in Blatt {ri.get('blatt')!r}, "
            f"Spalte {ri.get('spalte')} (Kopf {ri.get('spaltenkopf')!r}); {ri.get('werte')} Werte, "
            f"{ri.get('duplikate')} Duplikate, {ri.get('eindeutig')} eindeutig."
        )
        z.append(f"   Ohne Stückliste (MAST 4000/1): {len(ri.get('ohne_stueckliste', []))} "
                 f"{ri.get('ohne_stueckliste', [])[:20]}")  # fmt: skip
        z.append(f"   Abgleich `MATERIAL_LIST` ({ri.get('legacy')}): nur XLSX {len(ri.get('nur_xlsx', []))} "
                 f"{ri.get('nur_xlsx', [])[:20]}, nur Legacy {len(ri.get('nur_legacy', []))} "
                 f"{ri.get('nur_legacy', [])[:20]}")  # fmt: skip
    else:
        z.append("5. **Planzeiten-XLSX:** nicht geladen.")

    cabn = erg.protokoll.get("CABN")
    if cabn:
        gefunden = (
            set(erg.tabellen["CABN"]["ATNAM"].str.upper()) if "ATNAM" in erg.tabellen["CABN"] else set()
        )
        z.append(f"6. **CABN:** roh {cabn.zeilen_roh}, geladen {cabn.zeilen_geladen}; kanonische Merkmale ohne "
                 f"CABN-Zeile: {sorted(kanonisch - gefunden) or 'keine'}.")  # fmt: skip
    else:
        z.append("6. **CABN:** nicht geladen.")

    nullen = {t: p.fuehrende_nullen for t, p in erg.protokoll.items() if p.fuehrende_nullen is not None}
    z.append(f"7. **Führende Nullen in Materialnummern/STLNR (roh):** {nullen} – der Loader normalisiert.")

    grenze = [h for p in erg.protokoll.values() for h in p.hinweise if "Excel-Grenze" in h]
    z.append(
        f"8. **Excel-Grenze 1.048.576 Zeilen:** {'; '.join(grenze) if grenze else 'kein Blatt betroffen'}."
    )

    belegung = {
        t: f"{int(df['DATUV'].notna().sum())}/{len(df)} (roh z. B. {erg.protokoll[t].datum_beispiele[:3]})"
        for t, df in erg.tabellen.items()
        if "DATUV" in df.columns and len(df)
    }
    z.append(
        f"9. **DATUV belegt (lesbare Datumswerte / Zeilen):** {belegung or '–'} – 0 heißt: D14 greift dort nicht."
    )

    if "CUKB" in erg.tabellen:
        d = erg.tabellen["CUKB"]
        cols = [c for c in ("KNSTA", "KNART") if c in d.columns]
        if cols:
            vert = d.groupby(cols, dropna=False).size().to_dict()
            z.append(
                f"10. **CUKB KNSTA × KNART (roh):** {vert} – freigegeben gilt derzeit nur KNSTA = 1 (Q6)."
            )

    unbekannt = {t: p.unbekannte_spalten for t, p in erg.protokoll.items() if p.unbekannte_spalten}
    if unbekannt:
        z.append(f"\nUnbekannte Header (ins Mapping `basis_bom/headers.py` aufnehmen): {unbekannt}")
    for name, a in erg.abgleich.items():
        z.append(f"- Abgleich {name}: Datei {a['datei']}, berechnet {a['berechnet']}, nur Datei "
                 f"{a['anzahl_nur_datei']} {a['nur_datei'][:5]}, nur berechnet {a['anzahl_nur_berechnet']} "
                 f"{a['nur_berechnet'][:5]}")  # fmt: skip
    return "\n".join(z)


def schreibe_fragen(text: str, pfad: Path = config.FRAGEN_MD) -> None:
    """Ersetzt den generierten Abschnitt zwischen den Markern in docs/FRAGEN.md."""
    alt = pfad.read_text(encoding="utf-8") if pfad.exists() else "# Fragen an den Menschen\n"
    block = f"{START}\n{text}\n{ENDE}"
    if START in alt and ENDE in alt:
        neu = re.sub(re.escape(START) + r".*?" + re.escape(ENDE), lambda _: block, alt, flags=re.S)
    else:
        neu = alt.rstrip() + "\n\n## Prüfpunkte beim ersten Laden (generiert)\n\n" + block + "\n"
    pfad.write_text(neu, encoding="utf-8")
