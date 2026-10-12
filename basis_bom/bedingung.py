"""Quelltext des Beziehungswissens (SAP-Tabelle CUKN) → (Merkmal, Wert)-Paare (D5–D7, D11).

Merkmale und Werte einer Auswahlbedingung kommen aus dem Quelltext, nicht aus dem Namen `CUKB.KNNAM`: der Name
ist nur eine Bezeichnung und oft ungenau (`RUECKEN_FUNK=X,FUNKTION=X` hat den Text
`$parent.W_RUECKENVERST ='X' and $parent.W_FUNKTION = 'X'.`). Der Name-Parser (`parser.py`) bleibt Rückfallebene
für Bausteine ohne Text (`lies`).

Ergebnis im selben Format wie der Name-Parser (`parser.ParseErgebnis`: Paare UND-verknüpft), damit Ranking und
Auflösung unverändert bleiben. Ausgewertet wird nur, was sich ohne Raten in dieses Format bringen lässt:

- `M = 'v'`, `M EQ 'v'` → (M, v); `M IN ('a', 'b')` → (M, 'a/b') (Multi-Wert, D5).
- `M <> 'v'`, `M NE 'v'`, `NOT M = 'v'` → (M, '≠v') (Q47); `NOT M IN ('a', 'b')` → (M, '≠a/b').
- ODER nur zwischen Gleichheits-/IN-Vergleichen desselben Merkmals → ein Multi-Wert
  (`M = 'a' OR M = 'b'` → (M, 'a/b')).
- Nicht auswertbar (→ `manuell_prüfen` mit Grund, D11): ODER über verschiedene Merkmale, `specified`,
  Größenvergleiche (`>`, `<`, `>=`, `<=`), Funktionen, `TABLE`, Zuweisungen, Vergleiche zweier Merkmale.
  Aus dem Text entstehen keine Systemregel-Pseudo-Merkmale (D7 gilt nur für Namen).

Referenzen: `$PARENT.X`, `$SELF.X`, `$ROOT.X`, `$PARENT X` und bare `X`; Schlüsselwörter ohne Rücksicht auf
Groß-/Kleinschreibung, Merkmalsnamen und Werte in Großschrift (wie der Name-Parser). Werte in Hochkommas oder als
Zahl; Schlusspunkt optional; Klammern erlaubt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .parser import NICHT_GLEICH, ParseErgebnis, Parser

# Muster aus ranking.MULTI_TRENNER: ein Wert, der selbst einen Trenner enthält, ließe sich nicht mehr eindeutig teilen.
_MULTI = re.compile(r"[/+]")
MULTI = "/"

ZEILENLAENGE = 72  # SAP: Quelltext in Zeilen zu 72 Zeichen, davor 6-stellige Zeilenanzahl


# ---------------------------------------------------------------------------------------------------------
# Datenblock (CUKN.KNBLK) → Text


def dekodiere(knblk: object) -> str:
    """`000003$PARENT.A = 'X'␣␣…AND␣␣…` → `$PARENT.A = 'X' AND …`.

    Aufbau (aus den Exporten belegt): 6-stellige Zeilenanzahl, dann Zeilen zu 72 Zeichen (mit Leerzeichen
    aufgefüllt). Kommentarzeilen (`*` am Anfang) entfallen, die übrigen Zeilen werden mit einem Leerzeichen
    verbunden. Ohne Zahlenpräfix gilt der Block als fertiger Text (Zeilen an Zeilenumbrüchen).
    """
    if knblk is None:
        return ""
    s = str(knblk)
    if s.strip().lower() in {"", "nan", "none"}:
        return ""
    m = re.match(r"\s*(\d{6})", s)
    if m:
        rest = s[m.end() :]
        zeilen = [rest[i : i + ZEILENLAENGE] for i in range(0, len(rest), ZEILENLAENGE)]
    else:
        zeilen = s.splitlines()
    teile = [z.strip() for z in zeilen]
    return " ".join(z for z in teile if z and not z.startswith("*"))


def text_aus_bloecken(bloecke: list[tuple[object, object, object]]) -> str:
    """Blöcke eines Bausteins [(Blockzähler, Länge, KNBLK)] nach Blockzähler aneinanderhängen und dekodieren.

    Der Loader schneidet Leerzeichen am Ende eines Feldes ab; die Länge stellt das Auffüllen wieder her, damit das
    72er-Raster über Blockgrenzen hinweg stimmt.
    """

    def zahl(v: object) -> int | None:
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            return None

    teile = []
    for _, laenge, blk in sorted(bloecke, key=lambda b: (zahl(b[0]) is None, zahl(b[0]) or 0)):
        s = "" if blk is None else str(blk)
        n = zahl(laenge)
        teile.append(s.ljust(n) if n else s)
    return dekodiere("".join(teile))


# ---------------------------------------------------------------------------------------------------------
# Tokenizer

_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<ref>\$(?:PARENT|SELF|ROOT)\b\s*\.?\s*(?P<refname>[A-Z0-9_]+))
  | (?P<var>\$[A-Z_]+)
  | (?P<str>'(?P<strinhalt>[^']*)')
  | (?P<zahl>\d+(?:\.\d+)?(?![A-Z0-9_]))
  | (?P<wort>[A-Z0-9_]+)
  | (?P<op><>|>=|<=|=|<|>|\(|\)|,|\.|\*|\+|-|/)
    """,
    re.X | re.I,
)
SCHLUESSEL = {"AND", "OR", "NOT", "IN", "EQ", "NE", "GT", "LT", "GE", "LE", "SPECIFIED", "TABLE", "FUNCTION"}


@dataclass(frozen=True)
class _Tok:
    art: str  # name | wert | kw | op | ende
    text: str


class NichtAuswertbar(ValueError):
    pass


def _tokens(text: str) -> list[_Tok]:
    out, i = [], 0
    while i < len(text):
        m = _TOKEN.match(text, i)
        if m is None:
            raise NichtAuswertbar(f"unbekanntes Zeichen {text[i]!r}")
        i = m.end()
        if m.group("ws"):
            continue
        if m.group("ref"):
            out.append(_Tok("name", m.group("refname").upper()))
        elif m.group("var"):
            raise NichtAuswertbar(f"Variable {m.group('var')} nicht auswertbar")
        elif m.group("str") is not None:
            out.append(_Tok("wert", m.group("strinhalt").strip().upper()))
        elif m.group("zahl"):
            out.append(_Tok("wert", m.group("zahl")))
        elif m.group("wort"):
            w = m.group("wort").upper()
            out.append(_Tok("kw", w) if w in SCHLUESSEL else _Tok("name", w))
        else:
            out.append(_Tok("op", m.group("op")))
    out.append(_Tok("ende", ""))
    return out


# ---------------------------------------------------------------------------------------------------------
# Rekursiver Abstieg → Baum aus ("vgl", merkmal, werte, negiert) | ("und", [..]) | ("oder", [..]) | ("nicht", x)

_VERGLEICH = {">": ">", "<": "<", ">=": ">=", "<=": "<=", "GT": ">", "LT": "<", "GE": ">=", "LE": "<="}


class _Leser:
    def __init__(self, text: str) -> None:
        self.t = _tokens(text)
        self.i = 0

    def sieh(self) -> _Tok:
        return self.t[self.i]

    def nimm(self) -> _Tok:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def ist(self, art: str, text: str | None = None) -> bool:
        tok = self.sieh()
        return tok.art == art and (text is None or tok.text == text)

    def erwarte(self, art: str, text: str | None = None) -> _Tok:
        if not self.ist(art, text):
            gefunden = self.sieh().text or "Ende"
            raise NichtAuswertbar(f"Syntax: {text or art} erwartet, gefunden {gefunden!r}")
        return self.nimm()

    # bedingung := oder ['.'] ende
    def bedingung(self):
        baum = self.oder()
        if self.ist("op", "."):
            self.nimm()
        if self.ist("op", ","):
            raise NichtAuswertbar("Zuweisung/Aufzählung nicht auswertbar (Prozedur?)")
        self.erwarte("ende")
        return baum

    def oder(self):
        teile = [self.und()]
        while self.ist("kw", "OR"):
            self.nimm()
            teile.append(self.und())
        return teile[0] if len(teile) == 1 else ("oder", teile)

    def und(self):
        teile = [self.nicht()]
        while self.ist("kw", "AND"):
            self.nimm()
            teile.append(self.nicht())
        return teile[0] if len(teile) == 1 else ("und", teile)

    def nicht(self):
        if self.ist("kw", "NOT"):
            self.nimm()
            return ("nicht", self.nicht())
        return self.atom()

    def atom(self):
        if self.ist("op", "("):
            self.nimm()
            baum = self.oder()
            self.erwarte("op", ")")
            return baum
        if self.ist("kw", "TABLE"):
            raise NichtAuswertbar("TABLE (Variantentabelle) nicht auswertbar")
        if self.ist("kw", "FUNCTION"):
            raise NichtAuswertbar("Funktion nicht auswertbar")
        if self.ist("kw", "SPECIFIED"):
            raise NichtAuswertbar("specified nicht auswertbar")
        if self.ist("wert"):
            raise NichtAuswertbar("Syntax: Merkmal erwartet, gefunden Wert")
        merkmal = self.erwarte("name").text
        return self.vergleich(merkmal)

    def vergleich(self, merkmal: str):
        tok = self.sieh()
        if tok.art == "op" and tok.text == "(":
            raise NichtAuswertbar(f"Funktion {merkmal}(…) nicht auswertbar")
        if tok.art == "kw" and tok.text == "SPECIFIED":
            raise NichtAuswertbar(f"specified nicht auswertbar: {merkmal} specified")
        if tok.text in _VERGLEICH and tok.art in ("op", "kw"):
            raise NichtAuswertbar(f"Vergleich {_VERGLEICH[tok.text]} nicht auswertbar: {merkmal}")
        negiert = False
        if tok.art == "kw" and tok.text == "NOT":  # M NOT IN (…) / M NOT SPECIFIED
            self.nimm()
            negiert = True
            tok = self.sieh()
            if tok.art == "kw" and tok.text == "SPECIFIED":
                raise NichtAuswertbar(f"specified nicht auswertbar: {merkmal} not specified")
            if not (tok.art == "kw" and tok.text == "IN"):
                raise NichtAuswertbar(f"Syntax: IN erwartet nach {merkmal} NOT")
        if (tok.art, tok.text) in (("op", "="), ("kw", "EQ")):
            self.nimm()
            return ("vgl", merkmal, [self.wert(merkmal)], False)
        if (tok.art, tok.text) in (("op", "<>"), ("kw", "NE")):
            self.nimm()
            return ("vgl", merkmal, [self.wert(merkmal)], True)
        if tok.art == "kw" and tok.text == "IN":
            self.nimm()
            self.erwarte("op", "(")
            werte = [self.wert(merkmal)]
            while self.ist("op", ","):
                self.nimm()
                werte.append(self.wert(merkmal))
            self.erwarte("op", ")")
            return ("vgl", merkmal, werte, negiert)
        raise NichtAuswertbar(f"Syntax: Vergleich erwartet nach {merkmal}, gefunden {tok.text or 'Ende'!r}")

    def wert(self, merkmal: str) -> str:
        tok = self.sieh()
        if tok.art == "name":
            raise NichtAuswertbar(f"Vergleich zweier Merkmale nicht auswertbar: {merkmal}, {tok.text}")
        w = self.erwarte("wert").text
        if not w:
            raise NichtAuswertbar(f"leerer Wert bei {merkmal}")
        if _MULTI.search(w) or w.startswith(NICHT_GLEICH):
            raise NichtAuswertbar(
                f"Wert {w!r} enthält ein Trennzeichen (/, +) – als Multi-Wert nicht eindeutig"
            )
        return w


# ---------------------------------------------------------------------------------------------------------
# Baum → UND-Liste von Literalen (Merkmal, Werte, negiert)

Literal = tuple[str, tuple[str, ...], bool]


def _negiere(baum):
    art = baum[0]
    if art == "vgl":
        return ("vgl", baum[1], baum[2], not baum[3])
    if art == "nicht":
        return baum[1]
    if art == "und":
        return ("oder", [_negiere(b) for b in baum[1]])
    return ("und", [_negiere(b) for b in baum[1]])  # oder (De Morgan)


def _konjunktion(baum) -> list[Literal]:
    art = baum[0]
    if art == "vgl":
        return [(baum[1], tuple(dict.fromkeys(baum[2])), baum[3])]
    if art == "nicht":
        return _konjunktion(_negiere(baum[1]))
    if art == "und":
        return [lit for b in baum[1] for lit in _konjunktion(b)]
    # oder: nur Gleichheit/IN desselben Merkmals lässt sich als ein Multi-Wert schreiben
    teile = [_konjunktion(b) for b in baum[1]]
    if any(len(t) != 1 for t in teile):
        raise NichtAuswertbar("ODER über zusammengesetzte Bedingungen nicht auswertbar")
    lits = [t[0] for t in teile]
    if len({m for m, _, _ in lits}) > 1:
        raise NichtAuswertbar("ODER über verschiedene Merkmale nicht auswertbar: " +
                              ", ".join(dict.fromkeys(m for m, _, _ in lits)))  # fmt: skip
    if any(neg for _, _, neg in lits):
        raise NichtAuswertbar(f"ODER mit Verneinung nicht auswertbar: {lits[0][0]}")
    werte = tuple(dict.fromkeys(w for _, ws, _ in lits for w in ws))
    return [(lits[0][0], werte, False)]


@lru_cache(maxsize=65536)
def parse(text: str) -> ParseErgebnis:
    """Quelltext einer Auswahlbedingung → ParseErgebnis (Cache je Text)."""
    erg = ParseErgebnis(roh=text, quelle="text")
    if not (text or "").strip():
        erg.parsbar, erg.fehler = False, "leer"
        return erg
    try:
        lits = _konjunktion(_Leser(text).bedingung())
    except NichtAuswertbar as exc:
        erg.parsbar, erg.fehler = False, str(exc)
        return erg
    for merkmal, werte, negiert in lits:
        paar = (merkmal, (NICHT_GLEICH if negiert else "") + MULTI.join(werte))
        if paar not in erg.paare:
            erg.paare.append(paar)
    return erg


# ---------------------------------------------------------------------------------------------------------
# Eine Stelle für die Wahl Text/Name

TEXT, NAME = "text", "name"


def quelle(bez: dict) -> str:
    return TEXT if bez.get("text") else NAME


def lies(parser: Parser, bez: dict) -> ParseErgebnis:
    """Auswahlbedingung lesen: Quelltext (CUKN) vorhanden → Bedingungs-Parser, sonst Name (`KNNAM`, Rückfall)."""
    return parse(bez["text"]) if bez.get("text") else parser.parse(bez["knnam"])
