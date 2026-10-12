"""Regeln, Kürzel und Anzeigenamen von Legacy-Merkmalen auf SAP-Merkmale umschlüsseln (D6, D21).

Der Quelltext (CUKN) liefert die SAP-Merkmale (`W_FUNKTION`, `W_RUECKENVERST` …); nach D6 ist der kanonische Name
`CABN.ATNAM`. Die bisherigen Regeln, Kürzel und Anzeigenamen hängen an Namen aus den Bedingungsnamen
(`FUNKTION`, `RUECKEN_FUNK` …). Die Zuordnung Legacy → SAP wird aus den Daten abgeleitet: je Baustein mit Text wird
der Name (Name-Parser) mit dem Text (Bedingungs-Parser) verglichen, gleiche Werte bilden ein Paar, jedes Paar ist
ein Beleg. Vorgeschlagen wird nur, was eindeutig ist; mehrdeutige Merkmale werden gemeldet und lassen sich mit
`--zuordnung ALT=NEU` festlegen. Ausgeführt wird historisiert (D21) in einer Transaktion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import bedingung
from .parser import Parser
from .ranking import einzelwerte, negiert
from .rules import BASIS, OFFEN, Regelstand
from .source import KNART_AUSWAHL, SapSource

BEGRUENDUNG = "Umschlüsselung auf SAP-Merkmal (Quelltext CUKN)"


@dataclass
class Beleg:
    knnum: str
    knnam: str
    text: str
    alt: str
    neu: str
    wert: str
    reihenfolge: bool = False  # Wert kam mehrfach vor, gepaart über die Reihenfolge in Name und Text


@dataclass
class Vorschau:
    zuordnung: dict[str, str] = field(default_factory=dict)  # eindeutig, ALT ≠ NEU
    belege: dict[str, dict[str, list[Beleg]]] = field(default_factory=dict)  # ALT → NEU → Belege
    mehrdeutig: dict[str, dict[str, int]] = field(default_factory=dict)  # ALT → {NEU: Belege}
    gleich: dict[str, int] = field(default_factory=dict)  # ALT heißt im Text genauso
    ohne_paarung: list[dict] = field(default_factory=list)  # Name und Text passen nicht zusammen
    systemregeln: list[dict] = field(default_factory=list)  # Name ist Systemregel, Text nennt Merkmale
    abdeckung: dict = field(default_factory=dict)

    def zusammengefuehrt(self) -> dict[str, list[str]]:
        """NEU → mehrere ALT (Regeln landen im selben SAP-Merkmal; Konflikte möglich)."""
        out: dict[str, list[str]] = {}
        for alt, neu in self.zuordnung.items():
            out.setdefault(neu, []).append(alt)
        return {n: sorted(a) for n, a in out.items() if len(a) > 1}


def _schluessel(wert: str) -> tuple[bool, frozenset[str]]:
    neg, w = negiert(wert)
    return neg, frozenset(einzelwerte(w))


def paare_zuordnen(name_paare: list[tuple[str, str]], text_paare: list[tuple[str, str]]
                   ) -> tuple[list[tuple[str, str, str, bool]], list, list]:  # fmt: skip
    """Paare aus Name und Text über gleiche Werte verbinden → [(ALT, NEU, Wert, über Reihenfolge)], Reste.

    Ein Wert, der auf beiden Seiten genau einmal vorkommt, paart eindeutig. Kommt er auf beiden Seiten gleich oft
    vor (`RUECKEN_FUNK=X,FUNKTION=X` ↔ `W_RUECKENVERST = 'X' and W_FUNKTION = 'X'`), wird über die Reihenfolge
    gepaart (als solcher Beleg gekennzeichnet); sonst bleibt er ungepaart.
    """
    gruppen_n: dict = {}
    gruppen_t: dict = {}
    for m, w in name_paare:
        gruppen_n.setdefault(_schluessel(w), []).append((m, w))
    for m, w in text_paare:
        gruppen_t.setdefault(_schluessel(w), []).append((m, w))
    paare, rest_n, rest_t = [], [], []
    for k, ns in gruppen_n.items():
        ts = gruppen_t.get(k, [])
        if ns and len(ns) == len(ts):
            for (alt, w), (neu, _) in zip(ns, ts, strict=True):
                paare.append((alt, neu, w, len(ns) > 1))
        else:
            rest_n += ns
            rest_t += ts
    rest_t += [p for k, ts in gruppen_t.items() if k not in gruppen_n for p in ts]
    return paare, rest_n, rest_t


def leite_ab(src: SapSource, regeln: Regelstand) -> Vorschau:
    """Zuordnung Legacy-Merkmal → SAP-Merkmal aus allen Auswahlbedingungen mit Quelltext."""
    parser = Parser(regeln.alias_liste())
    knart_fehlt = "knart_fehlt" in src.marker
    v = Vorschau(abdeckung=src.quelltext_abdeckung())
    for knnum, bez in sorted(src.beziehungen.items(), key=lambda x: (len(x[0]), x[0])):
        if not bez.get("text") or not (knart_fehlt or bez["knart"] in KNART_AUSWAHL):
            continue
        t = bedingung.parse(bez["text"])
        n = parser.parse(bez["knnam"])
        if n.systemregel:
            if t.paare:
                r = regeln.regel(*n.paare[0])
                v.systemregeln.append({"knnum": knnum, "knnam": bez["knnam"], "text": bez["text"], "paare": t.paare,
                                       "status": r.status if r else None})  # fmt: skip
            continue
        if not (t.parsbar and n.parsbar and t.paare and n.paare):
            continue
        paare, rest_n, rest_t = paare_zuordnen(n.paare, t.paare)
        for alt, neu, wert, reihenfolge in paare:
            v.belege.setdefault(alt, {}).setdefault(neu, []).append(
                Beleg(knnum, bez["knnam"], bez["text"], alt, neu, wert, reihenfolge)
            )
        if rest_n or rest_t:
            v.ohne_paarung.append({"knnum": knnum, "knnam": bez["knnam"], "text": bez["text"], "name": rest_n,
                                   "quelltext": rest_t})  # fmt: skip
    for alt, ziele in sorted(v.belege.items()):
        zahl = {neu: len(b) for neu, b in ziele.items()}
        if len(zahl) > 1:
            v.mehrdeutig[alt] = dict(sorted(zahl.items(), key=lambda x: (-x[1], x[0])))
        elif alt in zahl:
            v.gleich[alt] = zahl[alt]
        else:
            v.zuordnung[alt] = next(iter(zahl))
    return v


# ---------------------------------------------------------------------------------------------------------
# Ausführen


@dataclass
class Bericht:
    regeln: list[tuple[str, str, str, str, int | None]] = field(
        default_factory=list
    )  # ALT, NEU, Wert, Status, Rang
    aliasse: list[tuple[str, str, str]] = field(default_factory=list)  # Kürzel, ALT, NEU
    namen: list[tuple[str, str, str]] = field(default_factory=list)  # ALT, NEU, Anzeigename
    konflikte: list[str] = field(default_factory=list)


def lies_zuordnung(texte: list[str] | None) -> dict[str, str]:
    """`ALT=NEU` (mehrfach) → {ALT: NEU}."""
    out = {}
    for t in texte or []:
        alt, sep, neu = t.partition("=")
        alt, neu = alt.strip().upper(), neu.strip().upper()
        if not sep or not alt or not neu:
            raise ValueError(f"Zuordnung {t!r}: Form ALT=NEU erwartet")
        out[alt] = neu
    return out


def fuehre_aus(eng: Engine, zuordnung: dict[str, str], von: str = "mensch") -> Bericht:
    """Regeln, Kürzel und Anzeigenamen umschlüsseln – historisiert (D21), alles in einer Transaktion.

    Regeln: jede gültige Regel ALT=Wert wird geschlossen und als NEU=Wert neu angelegt (Begründung „Umschlüsselung
    …“). Gibt es NEU=Wert schon mit einer Entscheidung (BASIS/NICHT_BASIS), die abweicht, oder ist der Rang in NEU
    belegt → Konflikt, ALT=Wert bleibt. Eine automatisch beobachtete OFFEN-Regel NEU=Wert wird ersetzt.
    Kürzel: alle Aliasse mit Merkmal ALT zeigen danach auf NEU; NEU bekommt einen Alias auf sich selbst.
    Anzeigename: NEU bekommt den Anzeigenamen von ALT, wenn NEU noch keinen hat (ALT behält seinen – die Startwerte in
    sql/schema/040_review.sql würden ihn beim nächsten `db init` ohnehin wieder anlegen).
    """
    b = Bericht()
    q = lambda con, sql, **p: con.execute(sa.text(sql), p)  # noqa: E731
    with eng.begin() as con:
        t = q(con, "SELECT clock_timestamp()").scalar()
        for alt, neu in sorted(zuordnung.items()):
            if alt == neu:
                continue
            if zuordnung.get(neu, neu) != neu:
                b.konflikte.append(f"{alt} → {neu}: {neu} wird selbst umgeschlüsselt (Kette) – übersprungen")
                continue
            aktiv = "gueltig_bis IS NULL"
            for rid, wert, status, rang, grund in q(con, "SELECT id, wert, status, rang, begruendung FROM basis_bom.regel "
                                                        f"WHERE merkmal = :m AND {aktiv} ORDER BY wert", m=alt).all():  # fmt: skip
                ziel = q(con, f"SELECT id, status, rang, gueltig_von FROM basis_bom.regel WHERE merkmal = :m AND "
                              f"wert = :w AND {aktiv}", m=neu, w=wert).first()  # fmt: skip
                if ziel and ziel.status != OFFEN and (ziel.status, ziel.rang) != (status, rang):
                    b.konflikte.append(f"{alt}={wert} ({status} {rang or ''}): Zielregel {neu}={wert} existiert schon "
                                       f"({ziel.status} {ziel.rang or ''}) – übersprungen")  # fmt: skip
                    continue
                if status == BASIS and (not ziel or ziel.status == OFFEN):
                    belegt = q(con, f"SELECT wert FROM basis_bom.regel WHERE merkmal = :m AND rang = :r AND "
                                    f"status = 'BASIS' AND wert <> :w AND {aktiv}", m=neu, r=rang, w=wert).scalar()  # fmt: skip
                    if belegt is not None:
                        b.konflikte.append(f"{alt}={wert} (BASIS {rang}): Rang {rang} ist in {neu} schon mit {belegt} "
                                           "belegt – übersprungen")  # fmt: skip
                        continue
                q(con, "UPDATE basis_bom.regel SET gueltig_bis = :t WHERE id = :i", t=t, i=rid)
                if ziel and (ziel.status, ziel.rang) == (status, rang):
                    b.regeln.append((alt, neu, wert, status, rang))  # gleiche Entscheidung steht schon in NEU
                    continue
                if ziel:  # OFFEN (beobachtet) wird durch die Entscheidung ersetzt
                    if ziel.gueltig_von == t:
                        q(con, "DELETE FROM basis_bom.regel WHERE id = :i", i=ziel.id)
                    else:
                        q(con, "UPDATE basis_bom.regel SET gueltig_bis = :t WHERE id = :i", t=t, i=ziel.id)
                text = f"{BEGRUENDUNG}, vorher {alt}" + (f"; {grund}" if grund else "")
                q(con, "INSERT INTO basis_bom.regel (merkmal, wert, status, rang, begruendung, gueltig_von, geaendert_von) "
                       "VALUES (:m, :w, :s, :r, :b, :t, :v)", m=neu, w=wert, s=status, r=rang, b=text, t=t, v=von)  # fmt: skip
                b.regeln.append((alt, neu, wert, status, rang))
            for aid, alias, status in q(con, "SELECT id, alias, status FROM basis_bom.alias WHERE merkmal = :m AND "
                                             f"{aktiv} ORDER BY alias", m=alt).all():  # fmt: skip
                q(con, "UPDATE basis_bom.alias SET gueltig_bis = :t WHERE id = :i", t=t, i=aid)
                q(con, "INSERT INTO basis_bom.alias (alias, merkmal, status, gueltig_von, geaendert_von) "
                       "VALUES (:a, :m, :s, :t, :v)", a=alias, m=neu, s=status, t=t, v=von)  # fmt: skip
                b.aliasse.append((alias, alt, neu))
            if q(con, f"SELECT 1 FROM basis_bom.alias WHERE alias = :a AND {aktiv}", a=neu).first() is None:
                q(con, "INSERT INTO basis_bom.alias (alias, merkmal, status, gueltig_von, geaendert_von) "
                       "VALUES (:a, :a, 'BASIS', :t, :v)", a=neu, t=t, v=von)  # fmt: skip
                b.aliasse.append((neu, neu, neu))
            name = q(con, "SELECT text FROM basis_bom.merkmal_text WHERE merkmal = :m", m=alt).scalar()
            schon = q(con, "SELECT text FROM basis_bom.merkmal_text WHERE merkmal = :m", m=neu).scalar()
            if name is not None and schon is None:
                q(con, "INSERT INTO basis_bom.merkmal_text (merkmal, text) VALUES (:m, :x)", m=neu, x=name)
                b.namen.append((alt, neu, name))
            elif name is not None and schon != name:
                b.konflikte.append(
                    f"Anzeigename: {neu} heißt schon „{schon}“ – „{name}“ von {alt} nicht übernommen"
                )
    return b


# ---------------------------------------------------------------------------------------------------------
# Ausgabe (CLI)


def vorschau_text(
    v: Vorschau, regeln: Regelstand, belege: int = 3, manuell: dict[str, str] | None = None
) -> str:
    manuell = manuell or {}
    z: list[str] = []
    a = v.abdeckung
    if not a.get("cukn"):
        z.append(
            "CUKN (Quelltext) fehlt – keine Zuordnung ableitbar; Bedingungen werden aus dem Namen gelesen."
        )
    z.append(f"Quelltext (CUKN): {a.get('mit_text', 0)} von {a.get('auswahl', 0)} Auswahlbedingungen mit Text, "
             f"{a.get('ohne_text', 0)} ohne (Rückfall: Name).")  # fmt: skip
    ziel = {**v.zuordnung, **manuell}
    z.append("")
    z.append("Zuordnung Legacy-Merkmal → SAP-Merkmal" + (" (eindeutig aus den Daten" +
             (", ergänzt um --zuordnung)" if manuell else ")") if ziel else ": keine"))  # fmt: skip
    for alt, neu in sorted(ziel.items()):
        bs = v.belege.get(alt, {}).get(neu, [])
        reihe = sum(x.reihenfolge for x in bs)
        herkunft = (
            "manuell (--zuordnung)"
            if alt in manuell
            else f"{len(bs)} {'Beleg' if len(bs) == 1 else 'Belege'}"
            + (f", davon {reihe} über die Reihenfolge" if reihe else "")
        )
        z.append(f"  {alt} → {neu}  ({herkunft})")
        for x in bs[:belege]:
            z.append(f"      {x.knnum} {x.knnam}  |  {x.text}")
        werte = sorted((r for r in regeln.regeln.values() if r.merkmal == alt),
                       key=lambda r: (r.status != BASIS, r.rang or 0, r.wert))  # fmt: skip
        kuerzel = sorted(al.alias for al in regeln.aliasse.values() if al.merkmal == alt)
        texte = [f"{r.wert} {r.status}" + (f" {r.rang}" if r.rang else "") for r in werte]
        z.append(f"      Regeln: {', '.join(texte) or '–'}")
        z.append(f"      Kürzel: {', '.join(kuerzel) or '–'}")
    for neu, alts in v.zusammengefuehrt().items():
        z.append(
            f"  Achtung: {', '.join(alts)} landen alle in {neu} – gleiche Werte/Ränge werden als Konflikt gemeldet."
        )
    if v.mehrdeutig:
        z.append("")
        z.append("Mehrdeutig (nicht vorgeschlagen; mit --zuordnung ALT=NEU festlegen):")
        for alt, ziele in v.mehrdeutig.items():
            gew = f" → festgelegt: {manuell[alt]}" if alt in manuell else ""
            z.append(f"  {alt}: " + ", ".join(f"{n} ({k})" for n, k in ziele.items()) + gew)
            for neu in ziele:
                for x in v.belege[alt][neu][:1]:
                    z.append(f"      {neu}: {x.knnum} {x.knnam}  |  {x.text}")
    if v.gleich:
        z.append("")
        z.append(
            "Im Text gleich benannt (nichts zu tun): " + ", ".join(f"{m} ({k})" for m, k in v.gleich.items())
        )
    if v.systemregeln:
        z.append("")
        z.append(f"Systemregel-Namen mit Quelltext ({len(v.systemregeln)}): die Bedingung wird jetzt über die Merkmale des "
                 "Texts entschieden, eine Entscheidung zur Systemregel wirkt dort nicht mehr:")  # fmt: skip
        for s in v.systemregeln[: belege * 3]:
            z.append(f"  {s['knnum']} {s['knnam']} (Regel: {s['status'] or 'keine'})  |  {s['text']}")
    if v.ohne_paarung:
        z.append("")
        z.append(
            f"Ohne Paarung ({len(v.ohne_paarung)} Bausteine: Werte aus Name und Text passen nicht zusammen):"
        )
        for o in v.ohne_paarung[: belege * 3]:
            z.append(f"  {o['knnum']} {o['knnam']}  |  {o['text']}")
    return "\n".join(z)
