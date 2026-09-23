"""Regel-, Alias- und Systemregel-Tabellen laden und pflegen (D1, D6–D8, D21)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Engine

BASIS, NICHT_BASIS, OFFEN = "BASIS", "NICHT_BASIS", "OFFEN"
SYSTEMWERT = "vorhanden"  # D7: Wert eines Pseudo-Merkmals (Systemregel)
SITZHOEHE = "SITZHOEHE"  # D3: numerischer Rang


@dataclass(frozen=True)
class Regel:
    merkmal: str
    wert: str
    status: str
    rang: int | None = None


@dataclass(frozen=True)
class Alias:
    alias: str
    merkmal: str | None
    status: str


@dataclass
class Regelstand:
    """Regelstand zu einem Zeitpunkt. `version` = Zeitstempel der letzten Änderung (D21)."""

    regeln: dict[tuple[str, str], Regel] = field(default_factory=dict)
    aliasse: dict[str, Alias] = field(default_factory=dict)
    version: dt.datetime | None = None

    @classmethod
    def aus_listen(
        cls, regeln: Iterable[Regel | tuple] = (), aliasse: Iterable[Alias | tuple] = (), version=None
    ) -> Regelstand:
        rs = [r if isinstance(r, Regel) else Regel(*r) for r in regeln]
        als = [a if isinstance(a, Alias) else Alias(*a) for a in aliasse]
        return cls({(r.merkmal, r.wert): r for r in rs}, {a.alias: a for a in als}, version)

    def regel(self, merkmal: str, wert: str) -> Regel | None:
        return self.regeln.get((merkmal, wert))

    def status(self, merkmal: str, wert: str) -> str | None:
        r = self.regel(merkmal, wert)
        return r.status if r else None

    def rangliste(self, merkmal: str) -> list[Regel]:
        """D1: BASIS-Werte eines Merkmals, Rang 1 zuerst."""
        return sorted(
            (r for r in self.regeln.values() if r.merkmal == merkmal and r.status == BASIS),
            key=lambda r: r.rang or 0,
        )

    def alias_liste(self) -> list[Alias]:
        """Alle Aliasse, längste zuerst (Parser-Reihenfolge, zur Laufzeit gebaut)."""
        return sorted(self.aliasse.values(), key=lambda a: (-len(a.alias), a.alias))

    def kanonische_merkmale(self) -> set[str]:
        return {a.merkmal for a in self.aliasse.values() if a.merkmal and a.status == BASIS}

    def mit_offen(self, paare: Iterable[tuple[str, str]]) -> Regelstand:
        """Kopie, in der unbekannte (Merkmal, Wert)-Paare als OFFEN stehen (D7, D8, Ersatz `cawn_fehlt`)."""
        neu = dict(self.regeln)
        for m, w in paare:
            neu.setdefault((m, w), Regel(m, w, OFFEN))
        return Regelstand(neu, dict(self.aliasse), self.version)


def lade_regelstand(eng: Engine, zeitpunkt: dt.datetime | None = None) -> Regelstand:
    """Regeln und Aliasse, die zum Zeitpunkt (Default: jetzt) gültig sind."""
    params = {"t": zeitpunkt or dt.datetime.now(dt.UTC)}
    gueltig = "gueltig_von <= :t AND (gueltig_bis IS NULL OR gueltig_bis > :t)"
    with eng.connect() as con:
        regeln = [
            Regel(*r)
            for r in con.execute(
                sa.text(f"SELECT merkmal, wert, status, rang FROM basis_bom.regel WHERE {gueltig}"), params
            )
        ]
        aliasse = [
            Alias(*a)
            for a in con.execute(
                sa.text(f"SELECT alias, merkmal, status FROM basis_bom.alias WHERE {gueltig}"), params
            )
        ]
        version = con.execute(
            sa.text(
                "SELECT max(t) FROM ("
                " SELECT gueltig_von AS t FROM basis_bom.regel UNION ALL SELECT gueltig_bis FROM basis_bom.regel"
                " UNION ALL SELECT gueltig_von FROM basis_bom.alias UNION ALL SELECT gueltig_bis FROM basis_bom.alias"
                ") x WHERE t <= :t"
            ),
            params,
        ).scalar()
    return Regelstand.aus_listen(regeln, aliasse, version)


def setze_regel(
    eng: Engine,
    merkmal: str,
    wert: str,
    status: str,
    rang: int | None = None,
    begruendung: str | None = None,
    geaendert_von: str = "mensch",
) -> None:
    """Historisierte Änderung (D21): aktive Zeile schließen, neue Zeile ab jetzt."""
    with eng.begin() as con:
        jetzt = con.execute(sa.text("SELECT clock_timestamp()")).scalar()
        con.execute(
            sa.text(
                "UPDATE basis_bom.regel SET gueltig_bis = :t "
                "WHERE merkmal = :m AND wert = :w AND gueltig_bis IS NULL"
            ),
            {"t": jetzt, "m": merkmal, "w": wert},
        )
        con.execute(
            sa.text(
                "INSERT INTO basis_bom.regel (merkmal, wert, status, rang, begruendung, gueltig_von, geaendert_von) "
                "VALUES (:m, :w, :s, :r, :b, :t, :v)"
            ),
            {
                "m": merkmal,
                "w": wert,
                "s": status,
                "r": rang,
                "b": begruendung,
                "t": jetzt,
                "v": geaendert_von,
            },
        )


def trage_offen_ein(eng: Engine, paare: Iterable[tuple[str, str]], geaendert_von: str) -> int:
    """D7/D8: neue (Merkmal, Wert)-Paare landen automatisch als OFFEN in der Regeltabelle."""
    werte = sorted(set(paare))
    if not werte:
        return 0
    with eng.begin() as con:
        res = con.execute(
            sa.text(
                "INSERT INTO basis_bom.regel (merkmal, wert, status, begruendung, geaendert_von) "
                "SELECT m, w, 'OFFEN', 'automatisch: im Lauf beobachtet', :v "
                "FROM unnest(CAST(:m AS text[]), CAST(:w AS text[])) AS x(m, w) "
                "WHERE NOT EXISTS (SELECT 1 FROM basis_bom.regel r WHERE r.merkmal = x.m AND r.wert = x.w "
                "                  AND r.gueltig_bis IS NULL)"
            ),
            {"m": [m for m, _ in werte], "w": [w for _, w in werte], "v": geaendert_von},
        )
        return res.rowcount


def trage_alias_offen_ein(eng: Engine, aliasse: Iterable[str], geaendert_von: str) -> int:
    """D6/D8: unbekannte Kürzel als OFFEN (ohne Merkmal) in die Alias-Tabelle."""
    werte = sorted(set(aliasse))
    if not werte:
        return 0
    with eng.begin() as con:
        res = con.execute(
            sa.text(
                "INSERT INTO basis_bom.alias (alias, merkmal, status, geaendert_von) "
                "SELECT a, NULL, 'OFFEN', :v FROM unnest(CAST(:a AS text[])) AS a "
                "WHERE NOT EXISTS (SELECT 1 FROM basis_bom.alias x WHERE x.alias = a AND x.gueltig_bis IS NULL)"
            ),
            {"a": werte, "v": geaendert_von},
        )
        return res.rowcount
