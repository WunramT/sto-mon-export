"""Logik der Web-Oberfläche: Material rechnen (mit Regel-Entwurf), Auswirkung, Übernehmen, Review.

Alle Berechnungen laufen über dieselbe Logik wie `basis-bom run` (explode/ranking) – es gibt keine zweite
Implementierung im Browser. Ein Entwurf ist eine Liste von Regel-/Kürzel-Änderungen, die der Browser hält und bei
jeder Anfrage mitschickt; gespeichert wird erst bei „Übernehmen“ (historisiert, D21).
"""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from .. import lauf, rules
from ..explode import (
    AUSGESCHLOSSEN,
    AUSGESCHLOSSEN_VERERBT,
    BASIS,
    EXPORT_STATUS,
    IGNORIERT,
    MANUELL_PRUEFEN,
    UNBEDINGT,
    UNTERHALB_MANUELL,
    Aufloeser,
)
from ..ranking import einzelwerte, negiert
from ..rules import Alias, Regel, Regelstand
from ..source import SapSource

log = logging.getLogger(__name__)

URTEILE = ("richtig", "fehlt", "gehoert_nicht_rein")
STATUS_TEXT = {
    BASIS: "Basis", UNBEDINGT: "immer enthalten", AUSGESCHLOSSEN: "ausgeschlossen",
    AUSGESCHLOSSEN_VERERBT: "ausgeschlossen (über Baugruppe)", MANUELL_PRUEFEN: "manuell prüfen",
    UNTERHALB_MANUELL: "unter manuell geprüfter Baugruppe", IGNORIERT: "ignoriert (Text/Dokument)",
}  # fmt: skip


def _wert_text(merkmal: str, wert: str) -> str:
    return f"{merkmal} ist gesetzt" if wert == rules.SYSTEMWERT else f"{merkmal} = {wert}"


FEHLER_TEXT = {
    "negation als Wort (NICHT/NOT) nicht auswertbar": "enthält eine Verneinung in Worten und kann nicht automatisch "
                                                      "ausgewertet werden",
    "leer": "ist leer",
    "leerzeichen": "hat eine unbekannte Schreibweise",
    "keine paare": "enthält keine erkennbaren Merkmale",
}  # fmt: skip


def _fehler_text(f: str) -> str:
    if f in FEHLER_TEXT:
        return FEHLER_TEXT[f]
    if f.startswith("unverständlich"):
        return "hat eine unbekannte Schreibweise"
    return "kann nicht gelesen werden"


def _liste(werte: list[str]) -> str:
    return werte[0] if len(werte) == 1 else ", ".join(werte[:-1]) + " und " + werte[-1]


def erklaere(
    status: str, grund: str, bedingungen: list[dict], gewaehlt: dict, eigener: str | None,
    kandidaten: dict | None = None,
) -> tuple[str, list[dict]]:  # fmt: skip
    """Kurze Erklärung in Alltagssprache und die offenen Fragen, die der Fachbereich klären kann."""
    kandidaten = kandidaten or {}
    fragen: list[dict] = []
    pruef = [p for b in bedingungen for p in b["pruefungen"]]
    for b in bedingungen:
        for k in b["unbekannte_kuerzel"] + b["offene_kuerzel"]:
            fragen.append({"typ": "kuerzel", "alias": k,
                           "text": f"Zu welchem Merkmal gehört das Kürzel „{k}“?"})  # fmt: skip
        if b["fehler"]:
            fragen.append(
                {"typ": "unlesbar", "text": f"Die Bedingung „{b['name']}“ {_fehler_text(b['fehler'])}"}
            )
        if b["rolle"] == "sonstige":
            fragen.append({"typ": "unlesbar", "text": f"Die Bedingung „{b['name']}“ hat eine unbekannte Art"})
    for p in pruef:
        if p["ergebnis"] != "manuell":
            continue
        m = p["merkmal"]
        werte = [k["wert"] for k in kandidaten.get(m, [])]
        if p["wert"] == rules.SYSTEMWERT or werte == [rules.SYSTEMWERT]:
            text = f"Gilt die technische Regel {m} in der Basis?"
        elif p["grund"].startswith("kein_rang_fuer:"):
            if len(werte) == 1:
                text = f"{m}: Auf dieser Stückliste kommt nur {werte[0]} vor – ist {werte[0]} ein Basiswert?"
            elif werte:
                text = f"{m}: Welcher der Werte {_liste(werte)} ist Basis?"
            else:
                text = f"{m}: Welcher Wert ist Basis?"
        else:
            offen = p["grund"].split(":", 1)[-1].split(" in ")[0].split("=", 1)[-1]
            text = f"{m}: Ist {offen.replace('/', ' bzw. ')} ein Basiswert? (steht in „{p['wert']}“)"
        fragen.append({"typ": "rang", "merkmal": m, "text": text})
    eindeutig = {(f["typ"], f.get("merkmal") or f.get("alias") or f["text"]): f for f in fragen}
    fragen = list(eindeutig.values())

    if status == BASIS:
        teile = [_wert_text(p["merkmal"], p["wert"].lstrip("≠")) + (" (≠)" if p["wert"].startswith("≠") else "")
                 for p in pruef if p["ergebnis"] == "passt"]  # fmt: skip
        return "Gehört zur Basis – Bedingung erfüllt: " + ", ".join(teile) + ".", fragen
    if status == UNBEDINGT:
        return "Immer enthalten – die Position hat keine Variantenbedingung.", fragen
    if status == AUSGESCHLOSSEN:
        nicht = [p for p in pruef if p["ergebnis"] == "passt_nicht"]
        teile = []
        for p in nicht:
            g = gewaehlt.get(p["merkmal"])
            if g is None and p["merkmal"] in gewaehlt:
                teile.append(f"{p['merkmal']} gehört laut Regel nie zur Basis")
            elif p["wert"].startswith("≠"):
                teile.append(f"verlangt {p['merkmal']} ≠ {p['wert'][1:]}, Basis ist aber {g}")
            else:
                teile.append(f"verlangt {p['merkmal']} = {p['wert']}, Basis ist {g}")
        return "Nicht in der Basis – " + "; ".join(teile) + ".", fragen
    if status == AUSGESCHLOSSEN_VERERBT:
        return "Nicht in der Basis, weil die übergeordnete Baugruppe ausgeschlossen ist.", fragen
    if status == UNTERHALB_MANUELL:
        return ("Liegt unter einer Baugruppe, die noch manuell geprüft werden muss "
                f"(eigene Bewertung: {STATUS_TEXT.get(eigener or '', eigener)})."), fragen  # fmt: skip
    if status == IGNORIERT:
        return "Text- oder Dokumentposition – nicht Teil der Stückliste.", fragen
    # manuell prüfen
    if grund.startswith("Klassenposition"):
        return "Klassenposition – welches Material eingesetzt wird, muss manuell entschieden werden.", fragen
    if grund.startswith("D15"):
        return "Die Baugruppe hat mehrere Stücklisten – bitte manuell prüfen.", fragen
    if grund.startswith("Datenfehler"):
        return "Zu dieser Bedingung fehlen Daten im SAP-Export – bitte manuell prüfen.", fragen
    if grund.startswith("Zyklus") or grund.startswith("maximale Tiefe"):
        return "Die Stückliste verweist auf sich selbst – bitte manuell prüfen.", fragen
    if grund.startswith("Positionstyp"):
        return f"Unbekannter Positionstyp – bitte manuell prüfen ({grund}).", fragen
    if fragen:
        return "Noch nicht entscheidbar – offene Frage" + (
            "n" if len(fragen) > 1 else ""
        ) + " siehe unten.", fragen
    return f"Bitte manuell prüfen ({grund}).", fragen


def _grund_text(grund: str | None) -> str | None:
    """Grund, warum ein Material nicht aufgelöst wird – in Fachsprache."""
    if not grund:
        return None
    if "KZKFG" in grund:
        return "In SAP nicht als konfigurierbares Material gekennzeichnet"
    if grund.startswith("D15"):
        return "Mehrere Stücklisten in Werk 4000 – bitte in SAP bereinigen"
    if grund.startswith("keine Stückliste"):
        return "Keine Stückliste in Werk 4000 (Verwendung 1)"
    if grund == "keine MARA-Zeile":
        return "Keine Stammdaten im Export"
    return grund


class Konflikt(Exception):
    def __init__(self, konflikte: list[dict]) -> None:
        super().__init__("Regelstand wurde inzwischen geändert")
        self.konflikte = konflikte


class Eingabefehler(ValueError):
    pass


@dataclass
class Entwurf:
    regeln: list[dict] = field(default_factory=list)  # {merkmal, wert, status, rang, vorher: {status, rang}}
    aliasse: list[dict] = field(default_factory=list)  # {alias, merkmal, status, vorher: {merkmal, status}}

    @classmethod
    def aus(cls, d: dict | None) -> Entwurf:
        d = d or {}
        return cls(list(d.get("regeln") or []), list(d.get("aliasse") or []))

    def leer(self) -> bool:
        return not self.regeln and not self.aliasse

    def schluessel(self) -> tuple:
        return (
            tuple(sorted((r["merkmal"], r["wert"], r["status"], r.get("rang")) for r in self.regeln)),
            tuple(sorted((a["alias"], a.get("merkmal") or "", a["status"]) for a in self.aliasse)),
        )


def ueberlagere(rs: Regelstand, e: Entwurf) -> Regelstand:
    regeln = dict(rs.regeln)
    for r in e.regeln:
        regeln[(r["merkmal"], r["wert"])] = Regel(r["merkmal"], r["wert"], r["status"], r.get("rang"))
    aliasse = dict(rs.aliasse)
    for a in e.aliasse:
        aliasse[a["alias"]] = Alias(a["alias"], a.get("merkmal") or None, a["status"])
    return Regelstand(regeln, aliasse, rs.version)


class Dienst:
    def __init__(self, eng: Engine) -> None:
        self.eng = eng
        self._lock = threading.Lock()
        self._src: SapSource | None = None
        self._cache: dict[tuple, Aufloeser] = {}
        self._erreichbar: dict[str, set[str]] | None = None

    # ---------------------------------------------------------------------------------------------------------
    @property
    def src(self) -> SapSource:
        with self._lock:
            if self._src is None:
                self._src = SapSource.from_db(self.eng)
            return self._src

    def neu_laden(self) -> None:
        with self._lock:
            self._src, self._cache, self._erreichbar = None, {}, None

    def regelstand(self) -> Regelstand:
        return rules.lade_regelstand(self.eng)

    def aufloeser(self, entwurf: Entwurf | None = None) -> Aufloeser:
        rs = self.regelstand()
        entwurf = entwurf or Entwurf()
        key = (str(rs.version), entwurf.schluessel())
        a = self._cache.get(key)
        if a is None:
            if len(self._cache) > 32:
                self._cache.clear()
            a = Aufloeser(self.src, ueberlagere(rs, entwurf))
            self._cache[key] = a
        return a

    def kurztext(self) -> dict[str, str]:
        return self.src.lookup("MAKT", "MAKTX")

    # ---------------------------------------------------------------------------------------------------------
    def _vorkommen(self, a: Aufloeser) -> tuple[Counter, Counter]:
        """(Merkmal, Wert) → Anzahl Stücklisten, Kürzel ohne Merkmal → Anzahl Stücklisten (alle Stücklisten)."""
        if getattr(a, "_ui_vorkommen", None) is None:
            werte: Counter = Counter()
            kuerzel: Counter = Counter()
            for _stlnr, pos in self.src.positionen.items():
                w_hier, k_hier = set(), set()
                for knobj in set(pos["KNOBJ"]) - {"", "0"}:
                    for knnum in self.src.knnum_pro_knobj.get(knobj, []):
                        bez = self.src.beziehungen.get(knnum)
                        if not bez:
                            continue
                        e = a.parser.parse(bez["knnam"])
                        for m, w in e.paare:
                            w_hier |= {(m, t) for t in einzelwerte(negiert(w)[1])}
                        k_hier |= set(e.unbekannte_aliasse) | set(e.offene_aliasse)
                werte.update(w_hier)
                kuerzel.update(k_hier)
            a._ui_vorkommen = (werte, kuerzel)
        return a._ui_vorkommen

    def offene_fragen(self, a: Aufloeser | None = None) -> int:
        a = a or self.aufloeser()
        werte, kuerzel = self._vorkommen(a)
        offen_werte = sum(1 for (m, w) in werte if m != rules.SITZHOEHE
                          and (a.regeln.status(m, w) in (None, rules.OFFEN)))  # fmt: skip
        return offen_werte + len(kuerzel)

    def meta(self) -> dict:
        s = self.src
        rs = self.regelstand()
        return {
            "stichtag": str(s.stichtag), "marker": sorted(s.marker), "warnungen": s.warnungen,
            "regel_version": str(rs.version) if rs.version else None,
            "regeln": len(rs.regeln), "offen": self.offene_fragen(),
        }  # fmt: skip

    def _roots(self) -> tuple[list[str], set[str]]:
        roots, aus = lauf.roots_aus_db(self.eng)
        return roots, set(aus)

    def materialien(self, q: str = "") -> list[dict]:
        roots, aus = self._roots()
        kt = self.kurztext()
        with self.eng.connect() as con:
            best = {r[0]: {"von": r[1], "datum": str(r[2])} for r in con.execute(
                sa.text("SELECT root_matnr, bestaetigt_von, datum FROM basis_bom.bestaetigt"))}  # fmt: skip
            in_arbeit = set(
                con.execute(sa.text("SELECT DISTINCT root_matnr FROM basis_bom.review")).scalars()
            )
        a = self.aufloeser()
        q = (q or "").strip().upper()
        out = []
        for m in roots:
            text = kt.get(m, "")
            if q and q not in m and q not in text.upper():
                continue
            grund = "Vom Fachbereich ausgeschlossen" if m in aus else _grund_text(a.root_pruefung(m))
            if m in best:
                zustand = "bestaetigt"
            elif grund:
                zustand = "nicht_aufloesbar"
            elif m in in_arbeit:
                zustand = "in_arbeit"
            else:
                zustand = "offen"
            out.append({"matnr": m, "kurztext": text, "zustand": zustand, "grund": grund,
                        "bestaetigt": best.get(m)})  # fmt: skip
        return out

    # ---------------------------------------------------------------------------------------------------------
    def _loese(self, a: Aufloeser, matnr: str) -> tuple[list[dict], list[str]]:
        erg = a.loese_alle([matnr])
        if erg.uebersprungen:
            raise Eingabefehler(f"{matnr} wird nicht aufgelöst: {erg.uebersprungen[0]['grund']}")
        return erg.zeilen, erg.warnungen

    def material(self, matnr: str, entwurf: Entwurf | None = None) -> dict:
        matnr = matnr.strip().lstrip("0")
        entwurf = entwurf or Entwurf()
        a = self.aufloeser(entwurf)
        zeilen, warnungen = self._loese(a, matnr)
        vorher = {}
        if not entwurf.leer():
            basis_zeilen, _ = self._loese(self.aufloeser(), matnr)
            vorher = {z["pfad"]: z["status"] for z in basis_zeilen}
        kt = self.kurztext()
        review = self.review(matnr, {z["pfad"]: z for z in zeilen} if entwurf.leer() else None)
        positionen = []
        for z in zeilen:
            sp = z["spur"]
            bed = []
            for b in sp.get("beziehungen", []):
                bed.append({
                    "name": b["knnam"], "rolle": b.get("rolle"), "fehler": b.get("fehler"),
                    "unbekannte_kuerzel": b.get("unbekannte_aliasse", []),
                    "offene_kuerzel": b.get("offene_aliasse", []),
                    "pruefungen": [{"merkmal": p["merkmal"], "wert": p["wert"], "ergebnis": p["ergebnis"],
                                    "grund": p["grund"]} for p in b.get("pruefungen", [])],
                })  # fmt: skip
            ebene = a._ebenen.get((z["stlnr"], sp.get("stlal", "1")))
            erkl, fragen = erklaere(z["status"], z["grund"] or "", bed, sp.get("gewaehlt", {}),
                                    sp.get("eigener_status"), ebene.wahl.kandidaten if ebene else None)  # fmt: skip
            v = vorher.get(z["pfad"])
            positionen.append({
                "id": z["pfad"], "parent": z["pfad"].rsplit("/", 1)[0], "ebene": z["ebene"], "posnr": z["posnr"],
                "matnr": z["matnr"], "kurztext": kt.get(z["matnr"], ""), "menge": z["menge"],
                "menge_kum": z["menge_kum"], "meins": z["meins"], "postp": z["postp"], "stlnr": z["stlnr"],
                "status": z["status"], "status_text": STATUS_TEXT.get(z["status"], z["status"]),
                "grund": z["grund"], "erklaerung": erkl, "fragen": fragen,
                "vorher": v if v and v != z["status"] else None,
                "bedingungen": bed, "prozeduren": sp.get("prozeduren", []),
                "gewaehlt": sp.get("gewaehlt", {}), "eigener_status": sp.get("eigener_status"),
                "im_ergebnis": z["status"] in EXPORT_STATUS,
            })  # fmt: skip
        ids = {p["id"] for p in positionen}
        for p in positionen:
            p["hat_kinder"] = False
        kinder = Counter(p["parent"] for p in positionen)
        for p in positionen:
            p["hat_kinder"] = kinder.get(p["id"], 0) > 0
        ebenen = {}
        for (stlnr, _alt), e in a._ebenen.items():
            if any(p["stlnr"] == stlnr for p in positionen):
                ebenen[stlnr] = {"bmeng": e.bmeng, "bmeng_angenommen": e.bmeng_angenommen,
                                 "gewaehlt": e.wahl.gewaehlt, "kandidaten": e.wahl.kandidaten,
                                 "marker": e.wahl.marker}  # fmt: skip
        return {
            "matnr": matnr, "kurztext": kt.get(matnr, ""), "warnungen": warnungen,
            "zaehler": dict(Counter(p["status"] for p in positionen)),
            "geaendert": sum(1 for p in positionen if p["vorher"]),
            "positionen": positionen, "ebenen": ebenen,
            "merkmale": self._merkmale_im_material(zeilen, a.regeln),
            "review": review, "ids": len(ids),
        }  # fmt: skip

    @staticmethod
    def _merkmale_im_material(zeilen: list[dict], rs: Regelstand) -> list[dict]:
        vorkommen: Counter = Counter()
        for z in zeilen:
            for b in z["spur"].get("beziehungen", []):
                for m, w in b.get("paare", []):
                    for t in einzelwerte(negiert(w)[1]):
                        vorkommen[(m, t)] += 1
        merkmale = sorted({m for m, _ in vorkommen})
        return [Dienst._merkmal_eintrag(m, rs, vorkommen) for m in merkmale]

    @staticmethod
    def _merkmal_eintrag(m: str, rs: Regelstand, vorkommen: Counter | None = None) -> dict:
        werte = {w for (mm, w) in rs.regeln if mm == m}
        if vorkommen:
            werte |= {w for (mm, w) in vorkommen if mm == m}
        eintraege = []
        for w in werte:
            r = rs.regel(m, w)
            eintraege.append({"wert": w, "status": r.status if r else rules.OFFEN, "rang": r.rang if r else None,
                              "vorkommen": (vorkommen or {}).get((m, w), 0)})  # fmt: skip
        eintraege.sort(
            key=lambda e: ({"BASIS": 0, "OFFEN": 1, "NICHT_BASIS": 2}[e["status"]], e["rang"] or 0, e["wert"])
        )
        return {"merkmal": m, "systemregel": [e["wert"] for e in eintraege] == [rules.SYSTEMWERT],
                "sitzhoehe": m == rules.SITZHOEHE, "werte": eintraege}  # fmt: skip

    # ---------------------------------------------------------------------------------------------------------
    def regeln(self, q: str = "", nur_offen: bool = False, entwurf: Entwurf | None = None) -> dict:
        a = self.aufloeser(entwurf)
        rs = a.regeln  # enthält die in Stücklisten beobachteten, noch nicht entschiedenen Werte als OFFEN
        werte_vk, kuerzel_vk = self._vorkommen(a)
        q = (q or "").strip().upper()
        merkmale = sorted({m for m, _ in rs.regeln})
        eintraege = []
        for m in merkmale:
            if q and q not in m:
                continue
            e = self._merkmal_eintrag(m, rs)
            for w in e["werte"]:
                w["stuecklisten"] = werte_vk.get((m, w["wert"]), 0)
            e["offen"] = sum(1 for w in e["werte"] if w["status"] == rules.OFFEN and w["stuecklisten"])
            eintraege.append(e)
        if nur_offen:
            eintraege = [e for e in eintraege if e["offen"] and not e["sitzhoehe"]]
        eintraege.sort(key=lambda e: (-e["offen"], e["merkmal"]))
        kuerzel = [{"alias": k, "merkmal": None, "status": rules.OFFEN, "stuecklisten": n}
                   for k, n in sorted(kuerzel_vk.items(), key=lambda x: (-x[1], x[0]))]  # fmt: skip
        return {"merkmale": eintraege, "kuerzel": kuerzel, "version": str(rs.version),
                "offen": self.offene_fragen(a)}  # fmt: skip

    def material_info(self, matnr: str) -> dict:
        m = matnr.strip().lstrip("0")
        s = self.src
        bekannt = (m in self.kurztext() or m in s.lookup("MARA", "MATKL") or m in s.stlnr_pro_material
                   or m in set(s.stpo["IDNRK"]))  # fmt: skip
        return {"matnr": m, "kurztext": self.kurztext().get(m, ""), "bekannt": bool(bekannt)}

    def entwurf_laden(self, name: str) -> dict | None:
        with self.eng.connect() as con:
            r = con.execute(
                sa.text("SELECT daten FROM basis_bom.entwurf WHERE name = :n"), {"n": name}
            ).scalar()
        return r

    def entwurf_speichern(self, name: str, daten: dict) -> None:
        if not name.strip():
            return
        leer = not (daten.get("regeln") or daten.get("aliasse"))
        with self.eng.begin() as con:
            if leer:
                con.execute(sa.text("DELETE FROM basis_bom.entwurf WHERE name = :n"), {"n": name})
            else:
                con.execute(sa.text(
                    "INSERT INTO basis_bom.entwurf (name, daten) VALUES (:n, CAST(:d AS jsonb)) "
                    "ON CONFLICT (name) DO UPDATE SET daten = EXCLUDED.daten, geaendert = now()"),
                    {"n": name, "d": json.dumps(daten)})  # fmt: skip

    # ---------------------------------------------------------------------------------------------------------
    def _stlnr_merkmale(self, a: Aufloeser) -> dict[str, set[str]]:
        """STLNR → Merkmale, die in ihren Auswahlbedingungen vorkommen (Index für die Breitenwirkung)."""
        out: dict[str, set[str]] = {}
        for stlnr, pos in self.src.positionen.items():
            ms: set[str] = set()
            for knobj in set(pos["KNOBJ"]) - {"", "0"}:
                for knnum in self.src.knnum_pro_knobj.get(knobj, []):
                    bez = self.src.beziehungen.get(knnum)
                    if bez:
                        e = a.parser.parse(bez["knnam"])
                        ms |= {m for m, _ in e.paare} | set(e.unbekannte_aliasse) | set(e.offene_aliasse)
            if ms:
                out[stlnr] = ms
        return out

    def _root_stuecklisten(self) -> dict[str, set[str]]:
        if self._erreichbar is None:
            s = self.src
            kinder = {k: set(v["IDNRK"]) for k, v in s.positionen.items()}
            out = {}
            roots, _ = self._roots()
            for r in roots:
                stls, offen, gesehen = set(), [r], set()
                while offen:
                    m = offen.pop()
                    if m in gesehen:
                        continue
                    gesehen.add(m)
                    for stlnr, _ in s.stlnr_pro_material.get(m, []):
                        if stlnr not in stls:
                            stls.add(stlnr)
                            offen.extend(kinder.get(stlnr, ()))
                out[r] = stls
            self._erreichbar = out
        return self._erreichbar

    def auswirkung(self, entwurf: Entwurf) -> dict:
        """Wirkung des Entwurfs auf alle Root-Materialien (nur die, deren Stücklisten betroffene Merkmale enthalten)."""
        if entwurf.leer():
            return {"materialien": [], "betroffen": 0, "geprueft": 0}
        alt, neu = self.aufloeser(), self.aufloeser(entwurf)
        merkmale = {r["merkmal"] for r in entwurf.regeln} | {a["alias"] for a in entwurf.aliasse} | {
            a["merkmal"] for a in entwurf.aliasse if a.get("merkmal")}  # fmt: skip
        index = self._stlnr_merkmale(neu)
        betroffene_stl = {s for s, ms in index.items() if ms & merkmale}
        roots, aus = self._roots()
        kt = self.kurztext()
        kandidaten = [
            r for r in roots if r not in aus and self._root_stuecklisten().get(r, set()) & betroffene_stl
        ]
        ergebnis = []
        for r in kandidaten:
            if alt.root_pruefung(r):
                continue
            vor = {z["pfad"]: z for z in alt.loese_alle([r]).zeilen}
            nach = {z["pfad"]: z for z in neu.loese_alle([r]).zeilen}
            wechsel = Counter()
            beispiele = []
            for pfad in vor.keys() | nach.keys():
                v, n = vor.get(pfad), nach.get(pfad)
                sv, sn = (v or {}).get("status"), (n or {}).get("status")
                if sv != sn:
                    wechsel[(sv, sn)] += 1
                    if len(beispiele) < 5:
                        z = n or v
                        beispiele.append({"matnr": z["matnr"], "kurztext": kt.get(z["matnr"], ""), "von": sv,
                                          "nach": sn})  # fmt: skip
            if wechsel:
                ergebnis.append({
                    "matnr": r, "kurztext": kt.get(r, ""), "geaendert": sum(wechsel.values()),
                    "wechsel": [{"von": a, "nach": b, "anzahl": n} for (a, b), n in wechsel.most_common()],
                    "beispiele": beispiele,
                    "vorher_im_ergebnis": sum(z["status"] in EXPORT_STATUS for z in vor.values()),
                    "nachher_im_ergebnis": sum(z["status"] in EXPORT_STATUS for z in nach.values()),
                })  # fmt: skip
        ergebnis.sort(key=lambda e: -e["geaendert"])
        return {"materialien": ergebnis, "betroffen": len(ergebnis), "geprueft": len(kandidaten)}

    # ---------------------------------------------------------------------------------------------------------
    def uebernehmen(self, entwurf: Entwurf, von: str, begruendung: str | None) -> dict:
        if not von.strip():
            raise Eingabefehler("Name fehlt")
        if entwurf.leer():
            raise Eingabefehler("Entwurf ist leer")
        rs = self.regelstand()
        konflikte = []
        for r in entwurf.regeln:
            akt = rs.regel(r["merkmal"], r["wert"])
            ist = {"status": akt.status if akt else rules.OFFEN, "rang": akt.rang if akt else None}
            soll = r.get("vorher") or {"status": rules.OFFEN, "rang": None}
            if (ist["status"], ist["rang"]) != (soll.get("status"), soll.get("rang")):
                konflikte.append({"art": "regel", "merkmal": r["merkmal"], "wert": r["wert"], "jetzt": ist,
                                  "beim_oeffnen": soll})  # fmt: skip
        for a in entwurf.aliasse:
            akt = rs.aliasse.get(a["alias"])
            ist = {"merkmal": akt.merkmal if akt else None, "status": akt.status if akt else None}
            soll = a.get("vorher") or {"merkmal": None, "status": None}
            if (ist["merkmal"], ist["status"]) != (soll.get("merkmal"), soll.get("status")):
                konflikte.append({"art": "kuerzel", "alias": a["alias"], "jetzt": ist, "beim_oeffnen": soll})
        if konflikte:
            raise Konflikt(konflikte)
        aenderungen = [rules.Aenderung(r["merkmal"], r["wert"], r["status"],
                                       r.get("rang") if r["status"] == rules.BASIS else None, begruendung)
                       for r in entwurf.regeln]  # fmt: skip
        for a in aenderungen:
            if a.status == rules.BASIS and not a.rang:
                raise Eingabefehler(f"{a.merkmal}={a.wert}: Basis braucht einen Rang")
        fehler = rules.pruefe_raenge(self.eng, aenderungen)
        if fehler:
            raise Eingabefehler("; ".join(fehler))
        aliasse = [
            rules.AliasAenderung(a["alias"], a.get("merkmal") or None, a["status"]) for a in entwurf.aliasse
        ]
        rules.uebernehme(self.eng, aenderungen, aliasse, von.strip())
        with self._lock:
            self._cache = {}
        return {"regeln": len(aenderungen), "kuerzel": len(aliasse)}

    # ---------------------------------------------------------------------------------------------------------
    # Review (D23, D24)

    def _letzter_review(self, matnr: str) -> list[dict]:
        with self.eng.connect() as con:
            return [dict(r) for r in con.execute(sa.text(
                "SELECT pfad, matnr, parent_matnr, menge, status, urteil, kommentar, reviewer, datum, lauf_id, importiert "
                "FROM basis_bom.review WHERE root_matnr = :m AND importiert = "
                "(SELECT max(importiert) FROM basis_bom.review WHERE root_matnr = :m)"), {"m": matnr}).mappings()]  # fmt: skip

    def review(self, matnr: str, aktuell: dict[str, dict] | None) -> dict:
        rows = self._letzter_review(matnr)
        with self.eng.connect() as con:
            best = con.execute(sa.text("SELECT bestaetigt_von, datum FROM basis_bom.bestaetigt WHERE root_matnr = :m"),
                               {"m": matnr}).first()  # fmt: skip
        urteile = {r["pfad"]: {"urteil": r["urteil"], "kommentar": r["kommentar"]} for r in rows
                   if r["pfad"] and r["status"] is not None}  # fmt: skip
        ergaenzt = [{"pfad": r["pfad"], "matnr": r["matnr"], "parent_matnr": r["parent_matnr"], "menge": r["menge"],
                     "kommentar": r["kommentar"]} for r in rows if r["status"] is None]  # fmt: skip
        veraltet = 0
        if aktuell is not None:
            veraltet = sum(
                1
                for r in rows
                if r["pfad"] in aktuell and r["status"] and aktuell[r["pfad"]]["status"] != r["status"]
            )
        return {
            "urteile": urteile, "ergaenzt": ergaenzt, "veraltet": veraltet,
            "stand": str(rows[0]["importiert"]) if rows else None, "von": rows[0]["reviewer"] if rows else None,
            "bestaetigt": {"von": best[0], "datum": str(best[1])} if best else None,
        }  # fmt: skip

    def review_speichern(self, matnr: str, urteile: dict[str, dict], ergaenzt: list[dict], von: str) -> dict:
        """Speichert den vollständigen Review-Stand als Momentaufnahme eines Laufs für dieses Material."""
        if not von.strip():
            raise Eingabefehler("Name fehlt")
        matnr = matnr.strip().lstrip("0")
        for pfad, u in urteile.items():
            if u.get("urteil") not in URTEILE:
                raise Eingabefehler(f"Urteil {u.get('urteil')!r} unbekannt ({pfad})")
        a = self.aufloeser()
        erg = a.loese_alle([matnr])
        if erg.uebersprungen:
            raise Eingabefehler(erg.uebersprungen[0]["grund"])
        zeilen = {z["pfad"]: z for z in erg.zeilen}
        unbekannt = [p for p in urteile if p not in zeilen]
        if unbekannt:
            raise Eingabefehler(
                f"{len(unbekannt)} Positionen gibt es im aktuellen Stand nicht mehr – Seite neu laden"
            )
        rs = self.regelstand()
        lauf_id = lauf.starte_lauf(self.eng, self.src, rs)
        lauf.speichere(self.eng, lauf_id, erg)
        lauf.beende_lauf(
            self.eng, lauf_id, "review", {"aufloesung": erg.statistik(), "quelle": "web", "von": von}
        )
        with self.eng.begin() as con:
            t = con.execute(sa.text("SELECT clock_timestamp()")).scalar()
            for pfad, u in urteile.items():
                z = zeilen[pfad]
                con.execute(sa.text(
                    "INSERT INTO basis_bom.review (root_matnr, matnr, parent_matnr, menge, status, urteil, kommentar,"
                    " reviewer, lauf_id, importiert, pfad) VALUES (:r, :m, :p, :q, :s, :u, :k, :v, :l, :t, :pf)"),
                    {"r": matnr, "m": z["matnr"], "p": z["parent_matnr"], "q": z["menge_kum"], "s": z["status"],
                     "u": u["urteil"], "k": u.get("kommentar") or None, "v": von, "l": lauf_id, "t": t, "pf": pfad})  # fmt: skip
            for e in ergaenzt:
                m = str(e.get("matnr") or "").strip().lstrip("0")
                if not m:
                    raise Eingabefehler("Ergänztes Material ohne Materialnummer")
                parent_pfad = e.get("parent_pfad") or matnr
                parent = zeilen[parent_pfad]["matnr"] if parent_pfad in zeilen else matnr
                con.execute(sa.text(
                    "INSERT INTO basis_bom.review (root_matnr, matnr, parent_matnr, menge, status, urteil, kommentar,"
                    " reviewer, lauf_id, importiert, pfad) VALUES (:r, :m, :p, :q, NULL, 'fehlt', :k, :v, :l, :t, :pf)"),
                    {"r": matnr, "m": m, "p": parent, "q": e.get("menge"), "k": e.get("kommentar") or None, "v": von,
                     "l": lauf_id, "t": t, "pf": f"{parent_pfad}/+:{m}"})  # fmt: skip
            con.execute(sa.text("DELETE FROM basis_bom.bestaetigt WHERE root_matnr = :r"), {"r": matnr})
        return {"lauf_id": lauf_id, "urteile": len(urteile), "ergaenzt": len(ergaenzt)}

    def bestaetigen(self, matnr: str, von: str) -> dict:
        matnr = matnr.strip().lstrip("0")
        rows = self._letzter_review(matnr)
        erg = self.aufloeser().loese_alle([matnr])
        aktuell = {z["pfad"]: z["status"] for z in erg.zeilen}
        urteile = {r["pfad"]: r for r in rows if r["status"] is not None}
        fehlend = [p for p in aktuell if p not in urteile]
        nicht_richtig = [r for r in rows if r["urteil"] != "richtig"]
        veraltet = [p for p, r in urteile.items() if aktuell.get(p) != r["status"]]
        if fehlend or nicht_richtig or veraltet:
            raise Eingabefehler(
                f"Bestätigen nicht möglich: {len(fehlend)} ohne Urteil, {len(nicht_richtig)} nicht „richtig“, "
                f"{len(veraltet)} mit geändertem Status seit dem Review"
            )
        with self.eng.begin() as con:
            con.execute(sa.text(
                "INSERT INTO basis_bom.bestaetigt (root_matnr, bestaetigt_von) VALUES (:r, :v) "
                "ON CONFLICT (root_matnr) DO UPDATE SET bestaetigt_von = :v, datum = current_date"),
                {"r": matnr, "v": von})  # fmt: skip
        return {"bestaetigt": matnr}
