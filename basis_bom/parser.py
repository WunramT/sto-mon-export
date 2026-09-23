"""Bedingungsnamen (CUKB.KNNAM) → (Merkmal, Wert)-Paare (D5–D7, D11).

Portiert `parse_beziehung` aus legacy/basis_bom_v0.py mit diesen Änderungen:
- Kürzel kommen aus der Alias-Tabelle (längste zuerst, zur Laufzeit gebaut), nicht aus Code.
- Ergebnis ist ein Objekt statt dict/None; nichts wird still verworfen (unbekannte Kürzel werden gemeldet).
- Keine Präfix-Heuristik für Systemregeln: ein Name ohne `=` ist Systemregel-Kandidat (D7).
- Negationen sind bis zur Klärung von F2 nicht parsbar.
- Multi-Werte (`BS/FK`) bleiben ungeteilt; die Aufteilung macht ranking.py (D5).

Syntax (aus den Legacy-Testfällen): Teile durch `,`; innerhalb eines Teils Tokens durch `_`. Token-Formen:
`ALIAS=WERT`, `ALIAS_WERT` (z. B. `SITZQ_HR`), `SH48` (Sitzhöhen-Alias + Ziffern), `46` (zweistellige Zahl =
SITZHOEHE, Legacy-Regel), `ALIAS WERT` als ganzer Name (z. B. `FUNKTION MANUEL`). Ein Wert endet vor dem
nächsten `_`, hinter dem ein Token beginnt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .rules import BASIS, SITZHOEHE, SYSTEMWERT, Alias

NEGATION = re.compile(r"<>|!=|\bNICHT\b|\bNOT\b")
_UNBEKANNT_START = re.compile(r"[A-Z0-9][A-Z0-9_]*?(?==)")
_UNBEKANNT_GRENZE = re.compile(r"[A-Z][A-Z0-9]*(?==)")
_ZAHL2 = re.compile(r"\d{2}(?=_|$)")


@dataclass
class ParseErgebnis:
    roh: str
    paare: list[tuple[str, str]] = field(default_factory=list)
    unbekannte_aliasse: list[str] = field(default_factory=list)
    offene_aliasse: list[str] = field(default_factory=list)  # Alias vorhanden, aber nicht BASIS (z. B. OPTIK)
    parsbar: bool = True
    systemregel: bool = False
    fehler: str | None = None

    @property
    def klasse(self) -> str:
        """Kategorie für Verteilungen (Notebook 10)."""
        if not self.parsbar:
            return "nicht_parsbar"
        if self.systemregel:
            return "systemregel_kandidat"
        if self.unbekannte_aliasse:
            return "unbekannter_alias"
        if self.offene_aliasse:
            return "offener_alias"
        return "parsbar"


class Parser:
    def __init__(self, aliasse: Iterable[Alias]) -> None:
        self.aliasse = sorted(aliasse, key=lambda a: (-len(a.alias), a.alias))
        self._namen = {a.alias for a in self.aliasse}
        self._sh = [a for a in self.aliasse if a.merkmal == SITZHOEHE and a.status == BASIS]
        self._cache: dict[str, ParseErgebnis] = {}

    # -----------------------------------------------------------------------------------------------------
    def parse(self, roh: str) -> ParseErgebnis:
        if roh not in self._cache:
            self._cache[roh] = self._parse(roh)
        return self._cache[roh]

    def _parse(self, roh: str) -> ParseErgebnis:
        erg = ParseErgebnis(roh=roh)
        s = re.sub(r"\s*=\s*", "=", (roh or "").strip().upper())
        if not s:
            return self._fehler(erg, "leer")
        if NEGATION.search(s):
            return self._fehler(erg, "negation (F2 offen)")
        m = re.fullmatch(r"([A-Z0-9_]+)\s+([A-Z0-9/+]+)", s)
        if m and m.group(1) in self._namen:
            s = f"{m.group(1)}={m.group(2)}"
        if re.search(r"\s", s):
            return self._fehler(erg, "leerzeichen")
        if "=" not in s:
            erg.systemregel = True
            erg.paare = [(s, SYSTEMWERT)]
            return erg
        for teil in (t.strip() for t in s.split(",")):
            if teil and not self._parse_teil(teil, erg):
                return erg
        if not erg.paare and not erg.unbekannte_aliasse and not erg.offene_aliasse:
            return self._fehler(erg, "keine paare")
        return erg

    @staticmethod
    def _fehler(erg: ParseErgebnis, grund: str) -> ParseErgebnis:
        erg.parsbar, erg.fehler, erg.paare = False, grund, []
        return erg

    # -----------------------------------------------------------------------------------------------------
    def _token(self, s: str, i: int, an_grenze: bool) -> tuple[Alias | str, int] | None:
        """Token ab Position i: (Alias oder unbekannter Schlüssel, Start des Werts) oder None."""
        for a in self.aliasse:
            if s.startswith(a.alias + "=", i):
                return a, i + len(a.alias) + 1
        for a in self.aliasse:
            if s.startswith(a.alias + "_", i):
                rest = s[i + len(a.alias) + 1 :]
                eq, sep = rest.find("="), rest.find("_")
                if rest and not rest.startswith("=") and (eq == -1 or (sep != -1 and sep < eq)):
                    return a, i + len(a.alias) + 1
        for a in self._sh:
            if s.startswith(a.alias, i) and re.match(r"\d{2,3}(?=_|$)", s[i + len(a.alias) :]):
                return a, i + len(a.alias)
        if _ZAHL2.match(s, i):
            return SITZHOEHE, i
        m = (_UNBEKANNT_GRENZE if an_grenze else _UNBEKANNT_START).match(s, i)
        if m:
            return "?" + m.group(0), m.end() + 1
        return None

    def _wert(self, s: str, j: int) -> tuple[str, int]:
        k = s.find("_", j)
        while k != -1:
            if self._token(s, k + 1, an_grenze=True) is not None:
                return s[j:k], k
            k = s.find("_", k + 1)
        return s[j:], len(s)

    def _parse_teil(self, s: str, erg: ParseErgebnis) -> bool:
        i = 0
        while i < len(s):
            if s[i] == "_":
                i += 1
                continue
            tok = self._token(s, i, an_grenze=False)
            if tok is None:
                self._fehler(erg, f"unverständlich ab {s[i:]!r}")
                return False
            ziel, j = tok
            if ziel == SITZHOEHE:  # zweistellige Zahl (Legacy-Regel)
                wert, i = s[j : j + 2], j + 2
            else:
                wert, i = self._wert(s, j)
            wert = wert.strip("_")
            if not wert:
                self._fehler(erg, f"leerer wert bei {s!r}")
                return False
            if isinstance(ziel, str) and ziel.startswith("?"):
                erg.unbekannte_aliasse.append(ziel[1:])
            elif isinstance(ziel, str):
                self._paar(erg, ziel, wert)
            elif ziel.status != BASIS or not ziel.merkmal:
                erg.offene_aliasse.append(ziel.alias)
            else:
                self._paar(erg, ziel.merkmal, wert)
        return True

    @staticmethod
    def _paar(erg: ParseErgebnis, merkmal: str, wert: str) -> None:
        if (merkmal, wert) not in erg.paare:
            erg.paare.append((merkmal, wert))
