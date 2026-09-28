"""Entscheidung pro Ebene (D1–D5, D7, D8).

Eingabe: alle (Merkmal, Wert)-Paare aus den Auswahlbedingungen einer Stückliste und der Regelstand.
Pro Merkmal gewinnt der vorkommende `BASIS`-Wert mit bestem Rang (D2), bei `SITZHOEHE` der niedrigste
vorkommende Zahlenwert (D3). Ohne Rangwert: Marker `kein_rang_fuer:<M>` (D4). Kein Blick nach oben/unten.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .rules import BASIS, NICHT_BASIS, OFFEN, SITZHOEHE, SYSTEMWERT, Regelstand

MULTI_TRENNER = re.compile(r"[/+]")

PASST, PASST_NICHT, MANUELL = "passt", "passt_nicht", "manuell"


NICHT_GLEICH = "≠"  # siehe parser.NICHT_GLEICH


def negiert(wert: str) -> tuple[bool, str]:
    """`≠HR` → (True, 'HR')."""
    return (True, wert[1:]) if wert.startswith(NICHT_GLEICH) else (False, wert)


def einzelwerte(wert: str) -> list[str]:
    """`BS/FK`, `FK+BS` → ['BS', 'FK'] (D5); ein Negationspräfix gehört nicht zum Wert."""
    return [t.strip() for t in MULTI_TRENNER.split(negiert(wert)[1]) if t.strip()]


def systemregel(kandidaten: list[dict]) -> bool:
    return [k["wert"] for k in kandidaten] == [SYSTEMWERT]


def _zahl(w: str) -> int | None:
    return int(w) if re.fullmatch(r"\d+", w) else None


@dataclass
class Ebenenwahl:
    gewaehlt: dict[str, str] = field(default_factory=dict)
    marker: list[str] = field(default_factory=list)
    kandidaten: dict[str, list[dict]] = field(default_factory=dict)  # für die Spur (D18)

    def kein_rang(self) -> set[str]:
        return {m.split(":", 1)[1] for m in self.marker if m.startswith("kein_rang_fuer:")}


@dataclass
class Pruefung:
    ergebnis: str  # passt | passt_nicht | manuell
    grund: str = ""


def waehle(paare: Iterable[tuple[str, str]], regeln: Regelstand) -> Ebenenwahl:
    werte: dict[str, set[str]] = {}
    for m, w in paare:
        werte.setdefault(m, set()).update(einzelwerte(w))
    wahl = Ebenenwahl()
    for m in sorted(werte):
        kand = []
        for w in sorted(werte[m], key=lambda x: (_zahl(x) is None, _zahl(x) or 0, x)):
            r = regeln.regel(m, w)
            kand.append({"wert": w, "status": r.status if r else None, "rang": r.rang if r else None})
        wahl.kandidaten[m] = kand
        if m == SITZHOEHE:
            zahlen = [(_zahl(k["wert"]), k["wert"]) for k in kand if _zahl(k["wert"]) is not None
                      and k["status"] != NICHT_BASIS]  # fmt: skip
            if zahlen:
                wahl.gewaehlt[m] = min(zahlen)[1]
            else:
                wahl.marker.append(f"kein_rang_fuer:{m}")
            continue
        basis = [k for k in kand if k["status"] == BASIS]
        if basis:
            wahl.gewaehlt[m] = min(basis, key=lambda k: k["rang"])["wert"]
            if any(k["status"] in (None, OFFEN) for k in kand):
                wahl.marker.append(f"offen_neben_rang:{m}")
        elif systemregel(kand) and kand[0]["status"] == NICHT_BASIS:
            wahl.gewaehlt[m] = None  # Systemregel gilt in der Basis nicht (Q20) → Positionen passen nicht
        else:
            wahl.marker.append(f"kein_rang_fuer:{m}")
    return wahl


def _unbekannt(m: str, w: str, regeln: Regelstand) -> bool:
    if m == SITZHOEHE:
        return _zahl(w) is None
    return regeln.status(m, w) in (None, OFFEN)


def pruefe_paar(merkmal: str, wert: str, wahl: Ebenenwahl, regeln: Regelstand) -> Pruefung:
    """Prüfung eines Paares gegen die Wahl der Ebene: enthalten-Semantik für Multi-Werte (D5)."""
    ist_negiert, wert = negiert(wert)
    if ist_negiert:  # „Merkmal ≠ Wert“ (Q47): Ergebnis der positiven Prüfung umkehren, MANUELL bleibt
        p = pruefe_paar(merkmal, wert, wahl, regeln)
        if p.ergebnis == MANUELL:
            return p
        g = wahl.gewaehlt.get(merkmal)
        if p.ergebnis == PASST:
            return Pruefung(PASST_NICHT, f"{merkmal}≠{wert}, gewählt ist {g}")
        return Pruefung(PASST, f"{merkmal}≠{wert} (gewählt {g})")
    if merkmal not in wahl.gewaehlt:
        return Pruefung(MANUELL, f"kein_rang_fuer:{merkmal}")
    g = wahl.gewaehlt[merkmal]
    if g is None:
        return Pruefung(PASST_NICHT, f"Systemregel {merkmal} ist NICHT_BASIS")
    teile = einzelwerte(wert)
    if merkmal == SITZHOEHE:
        treffer = any(_zahl(t) is not None and _zahl(t) == _zahl(g) for t in teile)
    else:
        treffer = g in teile
    if treffer:
        unbekannt = [t for t in teile if t != g and _unbekannt(merkmal, t, regeln)]
        if unbekannt:
            return Pruefung(MANUELL, f"unbekannter_teilwert:{merkmal}={'/'.join(unbekannt)} in {wert}")
        return Pruefung(PASST, f"{merkmal}={wert} ∋ {g}" if len(teile) > 1 else f"{merkmal}={g}")
    offen = [t for t in teile if _unbekannt(merkmal, t, regeln)]
    zusatz = f" (Status OFFEN/unbekannt: {'/'.join(offen)})" if offen else ""
    return Pruefung(PASST_NICHT, f"{merkmal}={wert} ≠ gewählt {g}{zusatz}")
