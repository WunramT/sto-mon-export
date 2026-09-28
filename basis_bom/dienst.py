"""Logik der Web-Oberfläche: Material rechnen (mit Regel-Entwurf), Auswirkung, Übernehmen, Review.

Alle Berechnungen laufen über dieselbe Logik wie `basis-bom run` (explode/ranking) – es gibt keine zweite
Implementierung im Browser. Ein Entwurf ist eine Liste von Regel-/Kürzel-Änderungen, die der Browser hält und bei
jeder Anfrage mitschickt; gespeichert wird erst bei „Übernehmen“ (historisiert, D21).
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import lauf, rules
from .explode import (
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
from .ranking import einzelwerte, negiert
from .rules import Alias, Regel, Regelstand
from .source import KNART_AUSWAHL, SapSource

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
    kandidaten: dict | None = None, namen: dict[str, str] | None = None,
) -> tuple[str, list[dict]]:  # fmt: skip
    """Kurze Erklärung in Alltagssprache und die offenen Fragen, die der Fachbereich klären kann."""
    kandidaten = kandidaten or {}
    namen = namen or {}
    fragen: list[dict] = []
    pruef = [p for b in bedingungen for p in b["pruefungen"]]
    for b in bedingungen:
        for k in b["unbekannte_kuerzel"] + b["offene_kuerzel"]:
            fragen.append({"typ": "kuerzel", "alias": k, "schluessel": f"kuerzel:{k}",
                           "text": f"Zu welchem Merkmal gehört das Kürzel „{k}“?"})  # fmt: skip
        if b["fehler"]:
            fragen.append({"typ": "unlesbar", "schluessel": f"unlesbar:{b['name']}",
                           "text": f"Die Bedingung „{b['name']}“ {_fehler_text(b['fehler'])}"})  # fmt: skip
        if b["rolle"] == "sonstige":
            fragen.append({"typ": "unlesbar", "schluessel": f"unlesbar:{b['name']}",
                           "text": f"Die Bedingung „{b['name']}“ hat eine unbekannte Art"})  # fmt: skip
    for p in pruef:
        if p["ergebnis"] != "manuell":
            continue
        m = p["merkmal"]
        n = namen.get(m, m)
        werte = [k["wert"] for k in kandidaten.get(m, [])]
        typ = "rang"
        if p["wert"] == rules.SYSTEMWERT or werte == [rules.SYSTEMWERT]:
            text, typ = f"Gilt die technische Regel „{n}“ in der Basis?", "systemregel"
        elif p["grund"].startswith("kein_rang_fuer:"):
            nie = [k["wert"] for k in kandidaten.get(m, []) if k.get("status") == rules.NICHT_BASIS]
            if werte and len(nie) == len(werte):
                text = (f"{n}: Hier kommt nur {_liste(werte)} vor und {'ist' if len(werte) == 1 else 'sind'} „Nie Basis“ – "
                        "welcher Wert soll auf dieser Stückliste doch gelten? Sonst die Position manuell entscheiden.")
            elif len(werte) == 1:
                text = f"{n}: Auf dieser Stückliste kommt nur {werte[0]} vor – ist {werte[0]} ein Basiswert?"
            elif werte:
                text = f"{n}: Welcher der Werte {_liste(werte)} ist Basis?"
            else:
                text = f"{n}: Welcher Wert ist Basis?"
        else:
            offen = p["grund"].split(":", 1)[-1].split(" in ")[0].split("=", 1)[-1]
            text = f"{n}: Ist {offen.replace('/', ' bzw. ')} ein Basiswert? (steht in „{p['wert']}“)"
        fragen.append({"typ": typ, "merkmal": m, "schluessel": f"merkmal:{m}", "text": text})
    eindeutig = {f["schluessel"]: f for f in fragen}
    fragen = list(eindeutig.values())

    if status == BASIS:
        teile = [f"{namen.get(p['merkmal'], p['merkmal'])} ist nicht {p['wert'][1:]}" if p["wert"].startswith("≠")
                 else _wert_text(namen.get(p["merkmal"], p["merkmal"]), p["wert"])
                 for p in pruef if p["ergebnis"] == "passt"]  # fmt: skip
        return "Gehört zur Basis – Bedingung erfüllt: " + ", ".join(teile) + ".", fragen
    if status == UNBEDINGT:
        return "Immer enthalten – die Position hat keine Variantenbedingung.", fragen
    if status == AUSGESCHLOSSEN:
        nicht = [p for p in pruef if p["ergebnis"] == "passt_nicht"]
        teile = []
        for p in nicht:
            g = gewaehlt.get(p["merkmal"])
            n = namen.get(p["merkmal"], p["merkmal"])
            if g is None and p["merkmal"] in gewaehlt:
                teile.append(f"die technische Regel „{n}“ gilt in der Basis nicht")
            elif p["wert"].startswith("≠"):
                teile.append(f"verlangt {n} nicht {p['wert'][1:]}, Basis ist aber {g}")
            else:
                teile.append(f"verlangt {n} = {p['wert']}, Basis ist {g}")
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
        nr = re.findall(r"\d+", grund[3:])
        return f"Mehrere Stücklisten ({', '.join(nr)}) in Werk 4000 – bitte in SAP bereinigen" if nr else \
            "Mehrere Stücklisten in Werk 4000 – bitte in SAP bereinigen"
    if grund.startswith("keine Stückliste"):
        return "Keine Stückliste in Werk 4000 (Verwendung 1)"
    if grund == "keine MARA-Zeile":
        return "Keine Stammdaten im Export"
    return grund


class Konflikt(Exception):
    def __init__(self, konflikte: list[dict], text: str = "Regelstand wurde inzwischen geändert") -> None:
        super().__init__(text)
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

    def cache_leeren(self) -> None:
        """Aufgelöste Stücklisten neu rechnen (z. B. nach geänderten Anzeigenamen); SAP-Daten bleiben geladen."""
        with self._lock:
            self._cache = {}

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
    def _vk(self, a: Aufloeser) -> dict:
        """Was in allen Stücklisten vorkommt: Werte, Kürzel ohne Merkmal, nicht lesbare Bedingungen (je Anzahl
        Stücklisten) und je Stückliste die Werte pro Merkmal."""
        if getattr(a, "_ui_vorkommen", None) is None:
            werte: Counter = Counter()
            kuerzel: Counter = Counter()
            unlesbar: Counter = Counter()
            fehler: dict[str, str] = {}
            beispiel: dict[str, list[str]] = {}  # "k:ALIAS" bzw. "w:MERKMAL|WERT" → Bedingungsnamen
            pro_stl: dict[str, dict[str, set[str]]] = {}
            for stlnr, pos in self.src.positionen.items():
                w_hier, k_hier, u_hier = set(), set(), set()
                for knobj in set(pos["KNOBJ"]) - {"", "0"}:
                    for knnum in self.src.knnum_pro_knobj.get(knobj, []):
                        bez = self.src.beziehungen.get(knnum)
                        if not bez or not (a.knart_fehlt or bez["knart"] in KNART_AUSWAHL):
                            continue  # Prozeduren wirken nicht auf die Auswahl (werden ignoriert)
                        e = a.parser.parse(bez["knnam"])
                        if e.fehler:
                            u_hier.add(bez["knnam"])
                            fehler[bez["knnam"]] = e.fehler
                        for m, w in e.paare:
                            for t in einzelwerte(negiert(w)[1]):
                                w_hier.add((m, t))
                                b = beispiel.setdefault(f"w:{m}|{t}", [])
                                if len(b) < 3 and bez["knnam"] not in b:
                                    b.append(bez["knnam"])
                        for k in set(e.unbekannte_aliasse) | set(e.offene_aliasse):
                            k_hier.add(k)
                            b = beispiel.setdefault(f"k:{k}", [])
                            if len(b) < 3 and bez["knnam"] not in b:
                                b.append(bez["knnam"])
                werte.update(w_hier)
                kuerzel.update(k_hier)
                unlesbar.update(u_hier)
                if w_hier:
                    d: dict[str, set[str]] = {}
                    for m, w in w_hier:
                        d.setdefault(m, set()).add(w)
                    pro_stl[stlnr] = d
            a._ui_vorkommen = {"werte": werte, "kuerzel": kuerzel, "unlesbar": unlesbar, "fehler": fehler,
                               "pro_stl": pro_stl, "beispiel": beispiel}  # fmt: skip
        return a._ui_vorkommen

    def _vorkommen(self, a: Aufloeser) -> tuple[Counter, Counter]:
        vk = self._vk(a)
        return vk["werte"], vk["kuerzel"]

    def merkmal_namen(self) -> dict[str, str]:
        with self.eng.connect() as con:
            return dict(con.execute(sa.text("SELECT merkmal, text FROM basis_bom.merkmal_text")).all())

    def merkmal_name_setzen(self, merkmal: str, text: str) -> None:
        merkmal, text = merkmal.strip().upper(), text.strip()
        if not merkmal:
            raise Eingabefehler("Merkmal fehlt")
        with self.eng.begin() as con:
            if text:
                con.execute(sa.text("INSERT INTO basis_bom.merkmal_text (merkmal, text) VALUES (:m, :t) "
                                    "ON CONFLICT (merkmal) DO UPDATE SET text = EXCLUDED.text"), {"m": merkmal, "t": text})  # fmt: skip
            else:
                con.execute(sa.text("DELETE FROM basis_bom.merkmal_text WHERE merkmal = :m"), {"m": merkmal})

    def fragen(self, a: Aufloeser | None = None) -> dict:
        """Die eine Liste offener Regelfragen (überall dieselbe Zählung) plus Hinweise, die nur in SAP lösbar sind.

        Je Merkmal eine Frage: beobachtete Werte ohne Entscheidung (OFFEN/unbekannt) oder Stücklisten, auf denen
        keiner der vorkommenden Werte Basis ist. Je Kürzel ohne Merkmal eine Frage.
        """
        a = a or self.aufloeser()
        if getattr(a, "_ui_fragen", None) is not None:
            return a._ui_fragen
        vk, rs, namen = self._vk(a), a.regeln, self.merkmal_namen()
        offen: dict[str, set[str]] = {}
        stl_offen: dict[str, set[str]] = {}
        ohne_basis: dict[str, set[str]] = {}
        for stlnr, d in vk["pro_stl"].items():
            for m, ws in d.items():
                if m == rules.SITZHOEHE:
                    continue
                st = {w: rs.status(m, w) for w in ws}
                o = {w for w, x in st.items() if x in (None, rules.OFFEN)}
                if o:
                    offen.setdefault(m, set()).update(o)
                    stl_offen.setdefault(m, set()).add(stlnr)
                elif rules.BASIS not in st.values() and ws != {rules.SYSTEMWERT}:
                    ohne_basis.setdefault(m, set()).add(stlnr)
        liste = []
        for m in sorted(set(offen) | set(ohne_basis)):
            name = namen.get(m, m)
            werte = sorted(offen.get(m, set()))
            stl = stl_offen.get(m, set()) | ohne_basis.get(m, set())
            if werte == [rules.SYSTEMWERT]:
                typ, text = "systemregel", f"Gilt die technische Regel „{name}“ in der Basis?"
            elif len(werte) == 1:
                typ, text = "merkmal", f"{name}: Ist {werte[0]} ein Basiswert?"
            elif werte:
                typ, text = "merkmal", f"{name}: Welche der Werte {_liste(werte)} sind Basiswerte?"
            else:
                typ, text = "merkmal", f"{name}: Auf manchen Stücklisten ist keiner der Werte Basis – welcher soll gelten?"
            bsp = sorted({b for w in werte for b in vk["beispiel"].get(f"w:{m}|{w}", [])})[:3]
            liste.append({"schluessel": f"merkmal:{m}", "typ": typ, "merkmal": m, "name": name, "werte": werte,
                          "text": text, "stuecklisten": len(stl), "beispiele": bsp})  # fmt: skip
        for k, n in sorted(vk["kuerzel"].items(), key=lambda x: (-x[1], x[0])):
            liste.append({"schluessel": f"kuerzel:{k}", "typ": "kuerzel", "alias": k,
                          "text": f"Zu welchem Merkmal gehört das Kürzel „{k}“?", "stuecklisten": n,
                          "beispiele": vk["beispiel"].get(f"k:{k}", [])})  # fmt: skip
        liste.sort(key=lambda f: -f["stuecklisten"])
        hinweise = [{"schluessel": f"unlesbar:{b}", "typ": "unlesbar", "bedingung": b,
                     "text": f"Die Bedingung „{b}“ {_fehler_text(vk['fehler'][b])} – bitte in SAP umformulieren "
                             "oder die betroffenen Positionen manuell bewerten.", "stuecklisten": n}
                    for b, n in sorted(vk["unlesbar"].items(), key=lambda x: (-x[1], x[0]))]  # fmt: skip
        a._ui_fragen = {"fragen": liste, "hinweise": hinweise}
        return a._ui_fragen

    def offene_fragen(self, a: Aufloeser | None = None) -> int:
        return len(self.fragen(a)["fragen"])

    def meta(self) -> dict:
        s = self.src
        rs = self.regelstand()
        return {
            "stichtag": str(s.stichtag), "marker": sorted(s.marker), "warnungen": s.warnungen,
            "regel_version": str(rs.version) if rs.version else None,
            "regeln": len(rs.regeln), "offen": self.offene_fragen(), "namen": self.merkmal_namen(),
            "merkmale": sorted({m for m, _ in rs.regeln} | {al.merkmal for al in rs.aliasse.values() if al.merkmal}),
            "kuerzel_beispiele": {k[2:]: v for k, v in self._vk(self.aufloeser())["beispiel"].items()
                                  if k.startswith("k:")},
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
                zustand = "bestaetigt_veraltet" if not grund and self._veraltet(a, m) else "bestaetigt"
            elif grund:
                zustand = "nicht_aufloesbar"
            elif m in in_arbeit:
                zustand = "in_arbeit"
            else:
                zustand = "offen"
            out.append({"matnr": m, "kurztext": text, "zustand": zustand, "grund": grund,
                        "bestaetigt": best.get(m)})  # fmt: skip
        return out

    def _veraltet(self, a: Aufloeser, matnr: str) -> int:
        """Anzahl Positionen, deren Status sich seit dem letzten Review geändert hat (0 = Bestätigung aktuell)."""
        rows = self._letzter_review(matnr)
        if not rows:
            return 0
        erg = a.loese_alle([matnr])
        aktuell = {z["pfad"]: z["status"] for z in erg.zeilen}
        return sum(1 for r in rows if r["status"] is not None and aktuell.get(r["pfad"]) != r["status"])

    # ---------------------------------------------------------------------------------------------------------
    def _loese(self, a: Aufloeser, matnr: str) -> tuple[list[dict], list[str]]:
        erg = a.loese_alle([matnr])
        if erg.uebersprungen:
            raise Eingabefehler(f"{matnr} kann nicht aufgelöst werden: {_grund_text(erg.uebersprungen[0]['grund'])}.")
        return erg.zeilen, erg.warnungen

    def material(self, matnr: str, entwurf: Entwurf | None = None) -> dict:
        matnr = matnr.strip().lstrip("0")
        roots, _aus = self._roots()
        if matnr not in set(roots):
            raise Eingabefehler(f"{matnr} ist kein Root-Material dieses Bereichs (Liste links). "
                                "Baugruppen öffnen Sie über das Material, in dem sie verbaut sind.")  # fmt: skip
        entwurf = entwurf or Entwurf()
        a = self.aufloeser(entwurf)
        zeilen, warnungen = self._loese(a, matnr)
        vorher = {}
        if not entwurf.leer():
            basis_zeilen, _ = self._loese(self.aufloeser(), matnr)
            vorher = {z["pfad"]: z["status"] for z in basis_zeilen}
        kt = self.kurztext()
        namen = self.merkmal_namen()
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
                                    sp.get("eigener_status"), ebene.wahl.kandidaten if ebene else None,
                                    namen)  # fmt: skip
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
        global_ = self.fragen(a)
        nach_schluessel = {f["schluessel"]: f for f in global_["fragen"] + global_["hinweise"]}
        im_material: dict[str, dict] = {}
        for p in positionen:
            for f in p["fragen"]:
                g = nach_schluessel.get(f["schluessel"], f)
                e = im_material.setdefault(f["schluessel"], {**g, "positionen": 0, "beispiel": p["id"]})
                e["positionen"] += 1
        mat_fragen = [f for f in im_material.values() if f["typ"] != "unlesbar"]
        mat_hinweise = [f for f in im_material.values() if f["typ"] == "unlesbar"]
        return {
            "matnr": matnr, "kurztext": kt.get(matnr, ""), "warnungen": warnungen,
            "offen": len(global_["fragen"]),
            "fragen": sorted(mat_fragen, key=lambda f: -f["positionen"]),
            "hinweise": sorted(mat_hinweise, key=lambda f: -f["positionen"]),
            "zaehler": dict(Counter(p["status"] for p in positionen)),
            "geaendert": sum(1 for p in positionen if p["vorher"]),
            "positionen": positionen, "ebenen": ebenen,
            "merkmale": self._merkmale_im_material(zeilen, a.regeln, namen),
            "review": review, "ids": len(ids),
        }  # fmt: skip

    @staticmethod
    def _merkmale_im_material(zeilen: list[dict], rs: Regelstand, namen: dict[str, str]) -> list[dict]:
        vorkommen: Counter = Counter()
        for z in zeilen:
            for b in z["spur"].get("beziehungen", []):
                for m, w in b.get("paare", []):
                    for t in einzelwerte(negiert(w)[1]):
                        vorkommen[(m, t)] += 1
        merkmale = sorted({m for m, _ in vorkommen})
        return [Dienst._merkmal_eintrag(m, rs, vorkommen, namen) for m in merkmale]

    @staticmethod
    def _merkmal_eintrag(m: str, rs: Regelstand, vorkommen: Counter | None = None,
                         namen: dict[str, str] | None = None) -> dict:  # fmt: skip
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
        return {"merkmal": m, "name": (namen or {}).get(m, m), "systemregel": [e["wert"] for e in eintraege] == [rules.SYSTEMWERT],
                "sitzhoehe": m == rules.SITZHOEHE, "werte": eintraege}  # fmt: skip

    # ---------------------------------------------------------------------------------------------------------
    def regeln(self, q: str = "", nur_offen: bool = False, entwurf: Entwurf | None = None) -> dict:
        a = self.aufloeser(entwurf)
        rs = a.regeln  # enthält die in Stücklisten beobachteten, noch nicht entschiedenen Werte als OFFEN
        werte_vk, kuerzel_vk = self._vorkommen(a)
        fr = self.fragen(a)
        frage_zu = {f["merkmal"]: f for f in fr["fragen"] if f.get("merkmal")}
        namen = self.merkmal_namen()
        q = (q or "").strip().upper()
        merkmale = sorted({m for m, _ in rs.regeln})
        eintraege = []
        for m in merkmale:
            if q and q not in m and q not in namen.get(m, "").upper():
                continue
            e = self._merkmal_eintrag(m, rs, None, namen)
            for w in e["werte"]:
                w["stuecklisten"] = werte_vk.get((m, w["wert"]), 0)
                w["beispiele"] = self._vk(a)["beispiel"].get(f"w:{m}|{w['wert']}", [])
            e["frage"] = frage_zu.get(m)
            e["offen"] = 1 if e["frage"] else 0
            eintraege.append(e)
        if nur_offen:
            im_entwurf = {r["merkmal"] for r in (entwurf.regeln if entwurf else [])}
            eintraege = [e for e in eintraege if e["frage"] or e["merkmal"] in im_entwurf]
        eintraege.sort(key=lambda e: (-e["offen"], e["name"].upper()))
        kuerzel = [{"alias": k, "merkmal": None, "status": rules.OFFEN, "stuecklisten": n}
                   for k, n in sorted(kuerzel_vk.items(), key=lambda x: (-x[1], x[0]))]  # fmt: skip
        return {"merkmale": eintraege, "kuerzel": kuerzel, "version": str(rs.version),
                "offen": len(fr["fragen"]), "fragen": fr["fragen"], "hinweise": fr["hinweise"]}  # fmt: skip

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
        with self.eng.connect() as con:
            best = set(con.execute(sa.text("SELECT root_matnr FROM basis_bom.bestaetigt")).scalars())
        for e in ergebnis:
            e["bestaetigt"] = e["matnr"] in best
        ergebnis.sort(key=lambda e: (not e["bestaetigt"], -e["geaendert"]))
        return {"materialien": ergebnis, "betroffen": len(ergebnis), "geprueft": len(kandidaten),
                "bestaetigt": sum(e["bestaetigt"] for e in ergebnis)}  # fmt: skip

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
            # fehlendes Kürzel = ohne Merkmal und OFFEN (so liefert es auch regeln() an die Oberfläche)
            ist = {"merkmal": akt.merkmal if akt else None, "status": akt.status if akt else rules.OFFEN}
            soll = a.get("vorher") or {"merkmal": None, "status": rules.OFFEN}
            if (ist["merkmal"] or None, ist["status"] or rules.OFFEN) != (soll.get("merkmal") or None,
                                                                          soll.get("status") or rules.OFFEN):
                konflikte.append({"art": "kuerzel", "alias": a["alias"], "jetzt": ist, "beim_oeffnen": soll})
        if konflikte:
            raise Konflikt(konflikte)
        if len((begruendung or "").strip()) < 5:
            raise Eingabefehler("Bitte kurz begründen (mindestens 5 Zeichen) – andere sollen die Entscheidung nachvollziehen können")
        begruendung = begruendung.strip()
        aenderungen = [rules.Aenderung(r["merkmal"], r["wert"], r["status"],
                                       r.get("rang") if r["status"] == rules.BASIS else None, begruendung)
                       for r in entwurf.regeln]  # fmt: skip
        for a in aenderungen:
            if a.status == rules.BASIS and not a.rang:
                raise Eingabefehler(f"{a.merkmal}={a.wert}: Basis braucht einen Rang")
        fehler = rules.pruefe_raenge(self.eng, aenderungen)
        if fehler:
            # doppelter Rang: jemand hat inzwischen einen anderen Wert auf denselben Rang gesetzt → Konflikt,
            # die Oberfläche lädt den Stand und nummeriert neu
            raise Konflikt([{"art": "rang", "merkmal": f.split(":", 1)[0], "text": f} for f in fehler],
                           "Die Rangfolge wurde inzwischen geändert")
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
                "SELECT pfad, matnr, parent_matnr, menge, meins, status, urteil, kommentar, reviewer, datum, lauf_id, importiert "
                "FROM basis_bom.review WHERE root_matnr = :m AND importiert = "
                "(SELECT max(importiert) FROM basis_bom.review WHERE root_matnr = :m)"), {"m": matnr}).mappings()]  # fmt: skip

    def review(self, matnr: str, aktuell: dict[str, dict] | None) -> dict:
        rows = self._letzter_review(matnr)
        with self.eng.connect() as con:
            best = con.execute(sa.text("SELECT bestaetigt_von, datum FROM basis_bom.bestaetigt WHERE root_matnr = :m"),
                               {"m": matnr}).first()  # fmt: skip
        urteile = {r["pfad"]: {"urteil": r["urteil"], "kommentar": r["kommentar"]} for r in rows
                   if r["pfad"] and r["status"] is not None}  # fmt: skip
        kt = self.kurztext()
        ergaenzt = [{"pfad": r["pfad"], "matnr": r["matnr"], "parent_matnr": r["parent_matnr"], "menge": r["menge"],
                     "meins": r["meins"] or "ST", "kurztext": kt.get(r["matnr"], ""), "kommentar": r["kommentar"]}
                    for r in rows if r["status"] is None]  # fmt: skip
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

    def review_speichern(self, matnr: str, urteile: dict[str, dict], ergaenzt: list[dict], von: str,
                         stand: str | None = None, pruefe_stand: bool = False) -> dict:  # fmt: skip
        """Speichert den vollständigen Review-Stand als Momentaufnahme eines Laufs für dieses Material.

        Mit `pruefe_stand`: `stand` ist der Review-Stand, auf dem die Eingaben beruhen (None = noch keiner). Hat
        inzwischen jemand anderes gespeichert, gibt es einen Konflikt statt stillem Überschreiben.
        """
        if not von.strip():
            raise Eingabefehler("Name fehlt")
        matnr = matnr.strip().lstrip("0")
        if pruefe_stand:
            self._pruefe_review_stand(matnr, stand)
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
            if pruefe_stand:
                # gleichzeitiges Speichern desselben Materials serialisieren und den Stand erneut prüfen
                con.execute(sa.text("SELECT pg_advisory_xact_lock(hashtext('review:' || :m))"), {"m": matnr})
                self._pruefe_review_stand(matnr, stand, con)
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
                    " reviewer, lauf_id, importiert, pfad, meins)"
                    " VALUES (:r, :m, :p, :q, NULL, 'fehlt', :k, :v, :l, :t, :pf, :e)"),
                    {"r": matnr, "m": m, "p": parent, "q": e.get("menge"), "k": e.get("kommentar") or None, "v": von,
                     "l": lauf_id, "t": t, "pf": f"{parent_pfad}/+:{m}", "e": e.get("meins") or "ST"})  # fmt: skip
            con.execute(sa.text("DELETE FROM basis_bom.bestaetigt WHERE root_matnr = :r"), {"r": matnr})
        return {"lauf_id": lauf_id, "urteile": len(urteile), "ergaenzt": len(ergaenzt)}

    def _pruefe_review_stand(self, matnr: str, stand: str | None, con=None) -> None:
        sql = sa.text("SELECT importiert, reviewer FROM basis_bom.review WHERE root_matnr = :m "
                      "ORDER BY importiert DESC LIMIT 1")  # fmt: skip
        if con is None:
            with self.eng.connect() as c:
                r = c.execute(sql, {"m": matnr}).first()
        else:
            r = con.execute(sql, {"m": matnr}).first()
        jetzt = str(r[0]) if r else None
        if jetzt != stand:
            wer = r[1] if r else "jemand"
            raise Konflikt([{"art": "review", "matnr": matnr, "von": wer, "stand": jetzt}],
                           f"{wer} hat dieses Material inzwischen bewertet")  # fmt: skip

    def bestaetigung_aufheben(self, matnr: str) -> None:
        with self.eng.begin() as con:
            con.execute(sa.text("DELETE FROM basis_bom.bestaetigt WHERE root_matnr = :r"), {"r": matnr.strip().lstrip("0")})

    @staticmethod
    def _offen(status: str | None) -> bool:
        return status in (MANUELL_PRUEFEN, UNTERHALB_MANUELL)

    def bestaetigen(self, matnr: str, von: str) -> dict:
        """Bestätigen (D23/D25): jede Position hat ein Urteil – regelentschiedene „richtig“, offene („manuell
        prüfen“) manuell „fehlt“/„gehoert_nicht_rein“ –, nichts ist seit dem Review veraltet."""
        if not von.strip():
            raise Eingabefehler("Name fehlt")
        matnr = matnr.strip().lstrip("0")
        rows = self._letzter_review(matnr)
        erg = self.aufloeser().loese_alle([matnr])
        aktuell = {z["pfad"]: z["status"] for z in erg.zeilen}
        urteile = {r["pfad"]: r for r in rows if r["status"] is not None}
        fehlend = [p for p in aktuell if p not in urteile]
        falsch = [p for p, r in urteile.items() if p in aktuell and (
            r["urteil"] not in ("fehlt", "gehoert_nicht_rein") if self._offen(aktuell[p]) else r["urteil"] != "richtig")]
        veraltet = [p for p, r in urteile.items() if aktuell.get(p) != r["status"]]
        ergaenzt = [r["pfad"].split("/+:")[0] for r in rows if r["status"] is None]
        widerspruch = self._widersprueche(aktuell, {p: r["urteil"] for p, r in urteile.items()}, ergaenzt)
        # Klassenposition „rein“ braucht das eingesetzte Material (ergänzt unter derselben Baugruppe)
        klassen = [z["pfad"] for z in erg.zeilen if not z["matnr"] and z["postp"] == "K"
                   and urteile.get(z["pfad"], {}).get("urteil") == "fehlt"]  # fmt: skip
        falsch += [p for p in klassen if p.rsplit("/", 1)[0] not in set(ergaenzt)]
        if fehlend or falsch or veraltet or widerspruch:
            teile = [f"{len(fehlend)} ohne Urteil", f"{len(falsch)} als falsch markiert",
                     f"{len(veraltet)} mit geändertem Status seit dem Review"]  # fmt: skip
            if widerspruch:
                teile.append(f"{len(widerspruch)} „Sollte rein“ unter einer ausgeschlossenen Baugruppe")
            raise Eingabefehler("Bestätigen nicht möglich: " + ", ".join(teile))
        with self.eng.begin() as con:
            con.execute(sa.text(
                "INSERT INTO basis_bom.bestaetigt (root_matnr, bestaetigt_von) VALUES (:r, :v) "
                "ON CONFLICT (root_matnr) DO UPDATE SET bestaetigt_von = :v, datum = current_date"),
                {"r": matnr, "v": von.strip()})  # fmt: skip
        return {"bestaetigt": matnr}

    def _widersprueche(self, aktuell: dict[str, str], urteile: dict[str, str], ergaenzt_unter: list[str] = ()) -> list[str]:
        """Positionen/Ergänzungen, die hineinsollen, deren Baugruppe aber nicht in der Basis ist (Regel oder manuell)."""
        raus = {p for p, st in aktuell.items()
                if (self._offen(st) and urteile.get(p) == "gehoert_nicht_rein")
                or (not self._offen(st) and st not in EXPORT_STATUS)}  # fmt: skip
        rein = [p for p, st in aktuell.items() if self._offen(st) and urteile.get(p) == "fehlt"]
        unter = lambda p: any(p == r or p.startswith(r + "/") for r in raus)  # noqa: E731
        return [p for p in rein if any(p.startswith(r + "/") for r in raus)] + [e for e in ergaenzt_unter if unter(e)]

    def export_zeilen(self, matnr: str):
        """Auflösung für den SAP-Format-Download: Regelergebnis plus die gespeicherten manuellen Entscheidungen
        (D25) – offene Positionen mit „fehlt“ kommen hinein, ergänzte Materialien werden angehängt."""
        import pandas as pd

        matnr = matnr.strip().lstrip("0")
        erg = self.aufloeser().loese_alle([matnr])
        if erg.uebersprungen:
            raise Eingabefehler(f"{matnr} kann nicht aufgelöst werden: {_grund_text(erg.uebersprungen[0]['grund'])}.")
        df = erg.df()
        rows = self._letzter_review(matnr)
        manuell = {r["pfad"]: r["urteil"] for r in rows if r["status"] is not None and self._offen(r["status"])}
        if manuell:
            offen = df["status"].isin([MANUELL_PRUEFEN, UNTERHALB_MANUELL])
            rein = offen & df["pfad"].map(lambda p: manuell.get(p) == "fehlt") & (df["matnr"] != "")
            df.loc[rein, "status"] = BASIS
            # unter einer nicht übernommenen Baugruppe kommt nichts in den Export
            draussen = [p for p, st in zip(df["pfad"], df["status"], strict=True) if st not in EXPORT_STATUS]
            unter = df["pfad"].map(lambda p: any(p.startswith(d + "/") for d in draussen))
            df.loc[unter & df["status"].isin(EXPORT_STATUS), "status"] = AUSGESCHLOSSEN_VERERBT
        drin = set(df.loc[df["status"].isin(EXPORT_STATUS), "pfad"]) | {matnr}
        neu = []
        for r in rows:
            if r["status"] is None and r["matnr"]:
                eltern = r["pfad"].split("/+:")[0]
                if eltern not in drin:
                    continue  # Baugruppe nicht in der Basis → Ergänzung darunter auch nicht (D26)
                ebene = eltern.count("/") + 1
                neu.append({"root_matnr": matnr, "lfd": 10**6 + len(neu), "ebene": ebene, "stlnr": "", "posnr": "",
                            "parent_matnr": r["parent_matnr"], "matnr": r["matnr"], "menge": r["menge"],
                            "menge_kum": r["menge"], "meins": r["meins"] or "ST", "postp": "L", "knobj": "",
                            "status": BASIS, "grund": "ergänzt (Review)", "pfad": r["pfad"], "spur": {}})  # fmt: skip
        if neu:
            df = pd.concat([df, pd.DataFrame(neu, columns=df.columns)], ignore_index=True)
        return df
