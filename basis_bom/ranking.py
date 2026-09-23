"""Entscheidung pro Ebene (D1–D5, D7, D8).

Eingabe: alle (Merkmal, Wert)-Paare aus den Auswahlbedingungen einer Stückliste und der Regelstand.
Pro Merkmal gewinnt der vorkommende `BASIS`-Wert mit bestem Rang (D2), bei `SITZHOEHE` der niedrigste
vorkommende Zahlenwert (D3). Ohne Rangwert: Marker `kein_rang_fuer:<M>` (D4). Kein Blick nach oben/unten.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .rules import BASIS, NICHT_BASIS, OFFEN, SITZHOEHE, Regelstand

MULTI_TRENNER = re.compile(r"[/+]")

PASST, PASST_NICHT, MANUELL = "passt", "passt_nicht", "manuell"


def einzelwerte(wert: str) -> list[str]:
    """`BS/FK`, `FK+BS` → ['BS', 'FK'] (D5)."""
    return [t.strip() for t in MULTI_TRENNER.split(wert) if t.strip()]


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
        else:
            wahl.marker.append(f"kein_rang_fuer:{m}")
    return wahl


def _unbekannt(m: str, w: str, regeln: Regelstand) -> bool:
    if m == SITZHOEHE:
        return _zahl(w) is None
    return regeln.status(m, w) in (None, OFFEN)


def pruefe_paar(merkmal: str, wert: str, wahl: Ebenenwahl, regeln: Regelstand) -> Pruefung:
    """Prüfung eines Paares gegen die Wahl der Ebene: enthalten-Semantik für Multi-Werte (D5)."""
    if merkmal not in wahl.gewaehlt:
        return Pruefung(MANUELL, f"kein_rang_fuer:{merkmal}")
    g = wahl.gewaehlt[merkmal]
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
