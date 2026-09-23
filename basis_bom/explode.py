"""Auflösung mit Bewertung und Spur (D9–D18). Ersetzt `explode_variant_bom_single` aus dem Legacy-Skript.

Ablauf pro Root-Material:
1. Root-Menge = root_material − root_ausschluss (D22); Stammdatenprüfung und D15 → sonst übersprungen.
2. BFS mit Pfad: ein Material unter zwei Eltern erzeugt zwei Zeilen (D16), pro Pfad nur einmal aufgelöst.
3. Pro Stückliste: Auswahlbedingungen aller Positionen parsen → Ranking (D2) → jede Position prüft alle
   Auswahlbedingungen mit UND (D9); Prozeduren werden gezählt, nicht bewertet (D10).
4. Status nach D11–D13, Vererbung nach D12; `menge_kum` nach D17; Spur nach D18.
"""

from __future__ import annotations

import logging
from collections import Counter, deque
from collections.abc import Iterable
from dataclasses import dataclass, field

import pandas as pd

from . import source as sapsource
from .parser import Parser
from .ranking import MANUELL, PASST_NICHT, Ebenenwahl, einzelwerte, pruefe_paar, waehle
from .rules import SITZHOEHE, Regelstand

log = logging.getLogger(__name__)

BASIS = "basis"
UNBEDINGT = "unbedingt"
AUSGESCHLOSSEN = "ausgeschlossen"
AUSGESCHLOSSEN_VERERBT = "ausgeschlossen_vererbt"
MANUELL_PRUEFEN = "manuell_prüfen"
UNTERHALB_MANUELL = "unterhalb_manuell"
IGNORIERT = "ignoriert"
EXPORT_STATUS = (BASIS, UNBEDINGT)  # D19

POSTP_AUFLOESEN = {"L", "N"}  # D13
POSTP_IGNORIERT = {"D", "T"}
POSTP_KLASSE = {"K"}

AUSWAHL, PROZEDUR, SONSTIGE = "auswahl", "prozedur_ignoriert", "sonstige"


@dataclass
class Optionen:
    max_tiefe: int = 20
    kzkfg_pruefen: bool = True  # Stammdatenregel D22: MARA KZKFG = X (Prüfung, nicht Quelle)
    vererbt_aufloesen: bool = True  # D12: Kinder ausgeschlossener Baugruppen sichtbar machen


@dataclass
class Ergebnis:
    zeilen: list[dict] = field(default_factory=list)
    ebene_marker: list[dict] = field(default_factory=list)
    uebersprungen: list[dict] = field(default_factory=list)
    lauf_marker: set[str] = field(default_factory=set)
    neue_paare: set[tuple[str, str]] = field(default_factory=set)
    neue_aliasse: set[str] = field(default_factory=set)
    warnungen: list[str] = field(default_factory=list)

    def df(self) -> pd.DataFrame:
        return pd.DataFrame(self.zeilen, columns=SPALTEN)

    def statistik(self) -> dict:
        status = Counter(z["status"] for z in self.zeilen)
        prozeduren = sum(len(z["spur"].get("prozeduren", [])) for z in self.zeilen)
        return {
            "roots_aufgeloest": len({z["root_matnr"] for z in self.zeilen}),
            "roots_uebersprungen": self.uebersprungen,
            "positionen": len(self.zeilen),
            "status": dict(sorted(status.items())),
            "prozeduren_ignoriert": prozeduren,
            "marker": sorted(self.lauf_marker),
            "ebene_marker": dict(Counter(m["marker"].split(":")[0] for m in self.ebene_marker)),
            "neue_offen_werte": len(self.neue_paare),
            "neue_offen_aliasse": sorted(self.neue_aliasse),
            "warnungen": self.warnungen,
        }


SPALTEN = ["root_matnr", "lfd", "ebene", "stlnr", "posnr", "parent_matnr", "matnr", "menge", "menge_kum", "meins",
           "postp", "knobj", "status", "grund", "pfad", "spur"]  # fmt: skip


@dataclass
class _Ebene:
    stlnr: str
    stlal: str
    bmeng: float
    bmeng_angenommen: bool
    wahl: Ebenenwahl
    positionen: list[dict]  # Bewertung ohne Vererbung


class Aufloeser:
    def __init__(
        self, src: sapsource.SapSource, regeln: Regelstand, optionen: Optionen | None = None
    ) -> None:
        self.src = src
        self.opt = optionen or Optionen()
        self.parser = Parser(regeln.alias_liste())
        self.knart_fehlt = "knart_fehlt" in src.marker
        self.neue_paare, self.neue_aliasse = self._beobachtet(regeln)
        # D7/D8 und Ersatz `cawn_fehlt`: beobachtete, unbekannte Werte gelten als OFFEN
        self.regeln = regeln.mit_offen(self.neue_paare)
        self.regel_version = regeln.version.isoformat() if regeln.version else None
        self._ebenen: dict[tuple[str, str], _Ebene] = {}

    # -----------------------------------------------------------------------------------------------------
    def _beobachtet(self, regeln: Regelstand) -> tuple[set[tuple[str, str]], set[str]]:
        paare, aliasse = set(), set()
        for bez in self.src.beziehungen.values():
            if not self.knart_fehlt and bez["knart"] not in sapsource.KNART_AUSWAHL:
                continue  # nur Auswahlbedingungen liefern Merkmalswerte (D10)
            e = self.parser.parse(bez["knnam"])
            aliasse.update(e.unbekannte_aliasse)
            for m, w in e.paare:
                for t in einzelwerte(w):
                    if m == SITZHOEHE or regeln.regel(m, t) is not None:
                        continue
                    paare.add((m, t))
        return paare, aliasse

    # -----------------------------------------------------------------------------------------------------
    def root_pruefung(self, matnr: str) -> str | None:
        """Grund, warum ein Root-Material nicht aufgelöst wird (D15, D22), sonst None."""
        stl = self.src.stlnr_pro_material.get(matnr, [])
        if not stl:
            return "keine Stückliste Werk 4000 Verwendung 1 (MAST)"
        if len({s for s, _ in stl}) > 1:
            return f"D15: mehrere STLNR {sorted({s for s, _ in stl})}"
        if self.opt.kzkfg_pruefen and self.src.mara is not None:
            kz = self.src.lookup("MARA", "KZKFG").get(matnr)
            if kz is None:
                return "keine MARA-Zeile"
            if kz.upper() != "X":
                return f"MARA KZKFG = {kz!r} statt 'X'"
        return None

    def loese_alle(self, roots: Iterable[str], ausschluss: Iterable[str] = ()) -> Ergebnis:
        erg = Ergebnis(
            lauf_marker=set(self.src.marker),
            neue_paare=self.neue_paare,
            neue_aliasse=self.neue_aliasse,
            warnungen=list(self.src.warnungen),
        )
        if self.src.mara is None and self.opt.kzkfg_pruefen:
            erg.warnungen.append("MARA fehlt – Stammdatenprüfung KZKFG nicht möglich")
        aus = set(ausschluss)
        for root in sorted(dict.fromkeys(roots)):
            if root in aus:
                erg.uebersprungen.append({"matnr": root, "grund": "root_ausschluss"})
                continue
            grund = self.root_pruefung(root)
            if grund:
                erg.uebersprungen.append({"matnr": root, "grund": grund})
                continue
            self._loese_auf(root, erg)
        return erg

    # -----------------------------------------------------------------------------------------------------
    def _beziehungen(self, knobj: str) -> tuple[list[dict], str | None]:
        """Beziehungen eines KNOBJ mit Rolle (D10); zweiter Wert = Datenfehler-Grund."""
        if knobj in ("", "0"):
            return [], None
        if knobj not in self.src.knobj_roh:
            return [], "knobj_ohne_cuob"
        out = []
        for knnum in self.src.knnum_pro_knobj.get(knobj, []):
            bez = self.src.beziehungen.get(knnum)
            if bez is None:
                if knnum not in self.src.knnum_roh:
                    return out, f"knnum_ohne_cukb:{knnum}"
                continue  # nur gelöschte/zukünftige/nicht freigegebene Versionen → wirkt nicht (D14)
            knart = bez["knart"]
            if self.knart_fehlt or knart in sapsource.KNART_AUSWAHL:
                rolle = AUSWAHL
            elif knart in sapsource.KNART_PROZEDUR:
                rolle = PROZEDUR
            else:
                rolle = SONSTIGE
            out.append({"knnum": knnum, "knnam": bez["knnam"], "knart": knart, "adzhl": bez["adzhl"],
                        "rolle": rolle})  # fmt: skip
        return out, None

    def _ebene(self, stlnr: str, stlal: str) -> _Ebene:
        key = (stlnr, stlal)
        if key in self._ebenen:
            return self._ebenen[key]
        pos = self.src.positionen_fuer(stlnr, stlal)
        roh = []
        paare = []
        for p in pos.to_dict("records"):
            bez, fehler = self._beziehungen(p.get("KNOBJ", ""))
            for b in bez:
                if b["rolle"] == AUSWAHL:
                    b["parse"] = self.parser.parse(b["knnam"])
                    paare += b["parse"].paare
            roh.append((p, bez, fehler))
        wahl = waehle(paare, self.regeln)  # D2: nur diese Stückliste
        bmeng, angenommen = self.src.bmeng(stlnr, stlal)
        ebene = _Ebene(stlnr, stlal, bmeng, angenommen, wahl, [])
        for p, bez, fehler in roh:
            ebene.positionen.append(self._bewerte(p, bez, fehler, wahl))
        self._ebenen[key] = ebene
        return ebene

    def _bewerte(self, p: dict, bez: list[dict], fehler: str | None, wahl: Ebenenwahl) -> dict:
        postp = str(p.get("POSTP", "")).upper()
        spur: dict = {"beziehungen": [], "prozeduren": []}
        if postp in POSTP_IGNORIERT:
            return {"p": p, "status": IGNORIERT, "grund": f"Positionstyp {postp} (D13)", "spur": spur}
        if postp in POSTP_KLASSE:
            return {"p": p, "status": MANUELL_PRUEFEN, "grund": "Klassenposition (D13)", "spur": spur}
        if postp not in POSTP_AUFLOESEN:
            return {"p": p, "status": MANUELL_PRUEFEN, "grund": f"Positionstyp {postp or '(leer)'} unbekannt (D13)",
                    "spur": spur}  # fmt: skip
        if fehler:
            return {"p": p, "status": MANUELL_PRUEFEN, "grund": f"Datenfehler: {fehler}", "spur": spur}

        nicht, manuell, passt = [], [], []
        relevant: set[str] = set()
        for b in bez:
            eintrag = {k: b[k] for k in ("knnum", "knnam", "knart", "adzhl", "rolle")}
            if b["rolle"] == PROZEDUR:
                spur["prozeduren"].append(b["knnam"])
            elif b["rolle"] == SONSTIGE:
                manuell.append(f"KNART {b['knart'] or '(leer)'} unbekannt: {b['knnam']}")
            else:
                e = b["parse"]
                eintrag.update(paare=e.paare, parsbar=e.parsbar, fehler=e.fehler,
                               unbekannte_aliasse=e.unbekannte_aliasse, offene_aliasse=e.offene_aliasse)  # fmt: skip
                if not e.parsbar:
                    manuell.append(f"nicht parsbar: {b['knnam']} ({e.fehler})")  # D11
                for a in e.unbekannte_aliasse:
                    manuell.append(f"unbekanntes Kürzel {a} in {b['knnam']}")  # D6
                for a in e.offene_aliasse:
                    manuell.append(f"Kürzel {a} nicht eindeutig/OFFEN in {b['knnam']}")  # D6
                pruef = []
                for m, w in e.paare:
                    relevant.add(m)
                    pr = pruefe_paar(m, w, wahl, self.regeln)
                    pruef.append({"merkmal": m, "wert": w, "ergebnis": pr.ergebnis, "grund": pr.grund})
                    if pr.ergebnis == PASST_NICHT:
                        nicht.append(pr.grund)
                    elif pr.ergebnis == MANUELL:
                        manuell.append(pr.grund)
                    else:
                        passt.append(pr.grund)
                eintrag["pruefungen"] = pruef
            spur["beziehungen"].append(eintrag)
        spur["gewaehlt"] = {m: wahl.gewaehlt.get(m) for m in sorted(relevant)}

        if nicht:  # D9: eine nicht passende Bedingung schließt aus
            status, grund = AUSGESCHLOSSEN, "; ".join(nicht)
        elif manuell:
            status, grund = MANUELL_PRUEFEN, "; ".join(manuell)
        elif any(b["rolle"] == AUSWAHL for b in bez):
            status, grund = BASIS, "; ".join(passt) or "Bedingung erfüllt"
        else:
            status = UNBEDINGT
            grund = "nur Prozeduren (ignoriert)" if spur["prozeduren"] else ""
        return {"p": p, "status": status, "grund": grund, "spur": spur}

    # -----------------------------------------------------------------------------------------------------
    def _loese_auf(self, root: str, erg: Ergebnis) -> None:
        stlnr, stlal = self.src.stlnr_pro_material[root][0]
        # (matnr, stlnr, stlal, ebene, pfad, pfad_matnr, menge_kum_parent, erbe, erbe_pfad)
        queue = deque([(root, stlnr, stlal, 1, root, (root,), 1.0, None, None)])
        lfd = 0
        markiert: set[str] = set()
        while queue:
            parent, stlnr, stlal, ebene_nr, pfad, pfad_mat, kum_parent, erbe, erbe_pfad = queue.popleft()
            ebene = self._ebene(stlnr, stlal)
            if stlnr not in markiert:
                markiert.add(stlnr)
                for m in ebene.wahl.marker:
                    art, _, merkmal = m.partition(":")
                    erg.ebene_marker.append(
                        {"root_matnr": root, "stlnr": stlnr, "marker": m, "merkmal": merkmal}
                    )
                if ebene.bmeng_angenommen:
                    erg.ebene_marker.append({"root_matnr": root, "stlnr": stlnr, "marker": "bmeng_angenommen",
                                             "merkmal": None})  # fmt: skip
            for bw in ebene.positionen:
                p = bw["p"]
                matnr = str(p.get("IDNRK", "") or "")
                posnr = str(p.get("POSNR", "") or "")
                menge = p.get("MENGE")
                menge = None if menge is None or pd.isna(menge) else float(menge)
                kum = None if menge is None or kum_parent is None else kum_parent * menge / ebene.bmeng  # D17
                status, grund = bw["status"], bw["grund"]
                spur = {**bw["spur"], "eigener_status": status, "regel_version": self.regel_version,
                        "stlal": stlal, "bmeng": ebene.bmeng, "bmeng_angenommen": ebene.bmeng_angenommen}  # fmt: skip
                # D12: Pfadvererbung
                eigen = f"eigene Bewertung {status}" + (f": {grund}" if grund else "")
                if erbe == AUSGESCHLOSSEN and status != IGNORIERT:
                    status, grund = (
                        AUSGESCHLOSSEN_VERERBT,
                        f"unter ausgeschlossener Baugruppe {erbe_pfad}; {eigen}",
                    )
                elif erbe == MANUELL_PRUEFEN and status not in (AUSGESCHLOSSEN, IGNORIERT):
                    status, grund = (
                        UNTERHALB_MANUELL,
                        f"unter manuell zu prüfender Baugruppe {erbe_pfad}; {eigen}",
                    )
                zeile_pfad = f"{pfad}/{posnr}:{matnr}"
                kinder = None
                if postp_aufloesen(p) and matnr in self.src.stlnr_pro_material:
                    stl = self.src.stlnr_pro_material[matnr]
                    if len({s for s, _ in stl}) > 1:  # D15
                        if status in EXPORT_STATUS:
                            status, grund = (
                                MANUELL_PRUEFEN,
                                f"D15: Baugruppe mit mehreren STLNR {[s for s, _ in stl]}",
                            )
                    elif matnr in pfad_mat:
                        status, grund = MANUELL_PRUEFEN, "Zyklus im Pfad"
                    elif ebene_nr >= self.opt.max_tiefe:
                        status, grund = MANUELL_PRUEFEN, f"maximale Tiefe {self.opt.max_tiefe} erreicht"
                    else:
                        kinder = stl[0]
                spur["status"], spur["grund"] = status, grund
                lfd += 1
                erg.zeilen.append({
                    "root_matnr": root, "lfd": lfd, "ebene": ebene_nr, "stlnr": stlnr, "posnr": posnr,
                    "parent_matnr": parent, "matnr": matnr, "menge": menge, "menge_kum": kum,
                    "meins": str(p.get("MEINS", "") or ""), "postp": str(p.get("POSTP", "") or ""),
                    "knobj": str(p.get("KNOBJ", "") or ""), "status": status, "grund": grund,
                    "pfad": zeile_pfad, "spur": spur,
                })  # fmt: skip
                if kinder is None:
                    continue
                if status in (AUSGESCHLOSSEN, AUSGESCHLOSSEN_VERERBT):
                    if not self.opt.vererbt_aufloesen:
                        continue
                    kind_erbe = AUSGESCHLOSSEN
                elif status in (MANUELL_PRUEFEN, UNTERHALB_MANUELL):
                    kind_erbe = MANUELL_PRUEFEN
                else:
                    kind_erbe = None
                kind_erbe_pfad = erbe_pfad if kind_erbe == erbe else zeile_pfad
                queue.append((matnr, kinder[0], kinder[1], ebene_nr + 1, zeile_pfad, (*pfad_mat, matnr), kum,
                              kind_erbe, kind_erbe_pfad))  # fmt: skip


def postp_aufloesen(p: dict) -> bool:
    return str(p.get("POSTP", "")).upper() in POSTP_AUFLOESEN
