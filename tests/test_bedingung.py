"""Quelltext des Beziehungswissens (CUKN): Dekodierung, Bedingungs-Parser, Wahl Text/Name, Laden und Auflösung."""

import pandas as pd
import pytest

from basis_bom import bedingung, loader
from basis_bom.explode import Aufloeser
from basis_bom.parser import Parser
from basis_bom.ranking import PASST_NICHT, pruefe_paar, waehle
from basis_bom.rules import Alias, Regel, Regelstand, seed_regelstand
from basis_bom.source import SapSource


def blk(*zeilen: str) -> str:
    """Datenblock im Format des Exports: 6-stellige Zeilenanzahl, Zeilen zu 72 Zeichen."""
    return f"{len(zeilen):06d}" + "".join(z.ljust(72) for z in zeilen)


# ---------------------------------------------------------------------------------------------------------
# Dekodierung


def test_dekodiere_72er_zeilen_und_kommentare():
    b = blk("* in die Funktion geht's rein", "$PARENT.W_FUNKTION = 'VZMO'", "AND", "$PARENT.W_SITZHOEHE = '45'.")
    assert len(b) == 6 + 72 * 4
    assert bedingung.dekodiere(b) == "$PARENT.W_FUNKTION = 'VZMO' AND $PARENT.W_SITZHOEHE = '45'."
    assert bedingung.dekodiere(b.rstrip()) == bedingung.dekodiere(b)  # abgeschnittene Auffüllung am Ende


def test_dekodiere_robust():
    assert bedingung.dekodiere("$parent.A = 'X'.") == "$parent.A = 'X'."  # ohne Zahlenpräfix
    assert bedingung.dekodiere("* Kommentar\n$parent.A = 'X'") == "$parent.A = 'X'"
    for leer in (None, "", "nan", float("nan"), blk("* nur Kommentar")):
        assert bedingung.dekodiere(leer) == ""


def test_bloecke_nach_blockzaehler_mit_laenge():
    voll = blk("$PARENT.A = 'X'", "AND", "$PARENT.B = 'Y'.")
    a, b = voll[:100], voll[100:]  # Block 2 beginnt mitten in der aufgefüllten Zeile „AND␣␣…“
    bloecke = [("1", len(b), b), ("0", len(a), a.rstrip())]  # Reihenfolge egal, Block 1 rechts gekürzt
    assert bedingung.text_aus_bloecken(bloecke) == "$PARENT.A = 'X' AND $PARENT.B = 'Y'."


# ---------------------------------------------------------------------------------------------------------
# Bedingungs-Parser: echte Beispiele aus EXPORT_CUKN_20261012_085449.xlsx

ECHT = [
    ("$parent.W_FUNKTION in ('VZMO').", [("W_FUNKTION", "VZMO")]),  # 14552 FUNKTION=VZMO
    ("$parent.W_FUNKTION = 'VZMO'.", [("W_FUNKTION", "VZMO")]),  # 14781 FUNK=VZMO
    ("$PARENT.W_FUNKTION = 'VZMO' AND $PARENT.W_SITZHOEHE = '45'.",  # 15055 FUNK=VZMO_SITZHOEHE=45
     [("W_FUNKTION", "VZMO"), ("W_SITZHOEHE", "45")]),
    ("$parent.W_RUECKENVERST ='X' and $parent.W_FUNKTION = 'X'.",  # 14608 RUECKEN_FUNK=X,FUNKTION=X
     [("W_RUECKENVERST", "X"), ("W_FUNKTION", "X")]),
    ("$parent.W_RUECKENVERST = 'STLR' and $parent.W_SITZHOEHE = '47'.",  # 14789
     [("W_RUECKENVERST", "STLR"), ("W_SITZHOEHE", "47")]),
    ("$PARENT.W_FUNKTION IN ('X') AND $PARENT.W_SITZHOEHE = '45'",  # 19840, ohne Schlusspunkt
     [("W_FUNKTION", "X"), ("W_SITZHOEHE", "45")]),
    ("$PARENT.SCH_ART = 'T25' or $PARENT.SCH_ART = 'PU2528'.", [("SCH_ART", "T25/PU2528")]),  # 15742
    ("$PARENT W_ARM_L in ('0')", [("W_ARM_L", "0")]),
]  # fmt: skip


@pytest.mark.parametrize(("text", "paare"), ECHT)
def test_echte_beispiele(text, paare):
    e = bedingung.parse(text)
    assert e.parsbar and e.fehler is None and e.quelle == "text" and not e.systemregel
    assert e.paare == paare


NICHT_AUSWERTBAR = [
    ("$PARENT.PP_KLIPS_CNC specified or $PARENT.PP_KLIPS_MENGE > 0.", "specified"),  # 25354 PP2000_KLIPS_CNC<>X
    ("function Z_SCHAUM_GET_WASTE ( INDEKS   = $parent.INDEKS, O_VBAP_WERKS = $parent.O_MARC_WERKS, "
     "O_STPO_MENGE = $self.G_STPO_ROME ).", "Funktion"),  # 12346 (Prozedur)
    ("$self.INDEKS2 = $parent.INDEKS, TABLE PP4000_P_ROZKROJ ( INDEKS = $self.INDEKS2 , W01 = $SELF.W01 ),",
     "Vergleich zweier Merkmale"),  # 15744 (Prozedur, Zuweisungen)
    ("TABLE PP4000_P_ROZKROJ (INDEKS = $self.INDEKS2)", "TABLE"),
    ("$parent.A = 'X' or $parent.B = 'Y'", "ODER über verschiedene Merkmale"),
    ("($parent.A = 'X' and $parent.B = 'Y') or $parent.A = 'Z'", "ODER über zusammengesetzte"),
    ("$parent.A <> 'X' or $parent.A <> 'Y'", "ODER mit Verneinung"),
    ("$PARENT.PP_KLIPS_MENGE > 0.", "Vergleich >"),
    ("$PARENT.MENGE GE 2", "Vergleich >="),
    ("$parent.A = 'B/C'", "Wert"),
    ("$parent.A = ''", "leerer Wert"),
    ("$parent.A = 'X' $parent.B = 'Y'", "Syntax"),
    ("", "leer"),
]  # fmt: skip


@pytest.mark.parametrize(("text", "grund"), NICHT_AUSWERTBAR)
def test_nicht_auswertbar_mit_grund(text, grund):
    e = bedingung.parse(text)
    assert not e.parsbar and e.paare == [] and e.fehler.startswith(grund), e.fehler


def test_negation_klammern_schluesselwoerter():
    p = lambda t: bedingung.parse(t).paare  # noqa: E731
    assert p("$parent.A <> 'X'") == p("$parent.A NE 'X'") == p("NOT $parent.A = 'X'") == [("A", "≠X")]
    assert p("not $parent.a in ('x', 'y').") == p("$PARENT.A NOT IN ('X','Y')") == [("A", "≠X/Y")]
    assert p("NOT ($parent.A = 'X' OR $parent.A = 'Y')") == [("A", "≠X"), ("A", "≠Y")]  # De Morgan
    assert p("$parent.A EQ 'x' AND ($parent.B = 'Y' OR $parent.B IN ('Z', 'Y'))") == [("A", "X"), ("B", "Y/Z")]
    assert p("$SELF.A = 45 and $ROOT.B = '1' and C = 'c'.") == [("A", "45"), ("B", "1"), ("C", "C")]


def test_cache_je_text():
    assert bedingung.parse("$parent.A = 'X'") is bedingung.parse("$parent.A = 'X'")


def test_negierter_multiwert_im_ranking():
    """`≠A/B` mit gewähltem A passt sicher nicht – auch wenn B unbekannt ist (sonst wäre NOT IN nicht auswertbar)."""
    rs = Regelstand.aus_listen([Regel("M", "A", "BASIS", 1)])
    wahl = waehle([("M", "A"), ("M", "≠A/B")], rs)
    assert pruefe_paar("M", "≠A/B", wahl, rs).ergebnis == PASST_NICHT
    assert pruefe_paar("M", "≠C/B", wahl, rs).ergebnis == "passt"


# ---------------------------------------------------------------------------------------------------------
# Wahl Text/Name (Rückfall) und Merkmalsnamen des Name-Parsers


def test_lies_text_sonst_name():
    parser = Parser(seed_regelstand().alias_liste())
    mit = bedingung.lies(parser, {"knnam": "FUNK=VZMO", "text": "$parent.W_FUNKTION = 'VZMO'."})
    ohne = bedingung.lies(parser, {"knnam": "FUNK=VZMO", "text": None})
    assert (mit.paare, mit.quelle) == ([("W_FUNKTION", "VZMO")], "text")
    assert (ohne.paare, ohne.quelle) == ([("FUNKTION", "VZMO")], "name")
    assert bedingung.quelle({"text": "x"}) == "text" and bedingung.quelle({"text": None}) == "name"


def test_name_parser_nach_umschluesselung_liefert_sap_namen():
    """Zweistellige Zahl und `SH48` folgen dem Kürzel SITZHOEHE/SH – nach der Umschlüsselung also W_SITZHOEHE."""
    aliasse = [Alias("SITZHOEHE", "W_SITZHOEHE", "BASIS"), Alias("SH", "W_SITZHOEHE", "BASIS"),
               Alias("FUNKTION", "W_FUNKTION", "BASIS"), Alias("FUNK", "W_FUNKTION", "BASIS")]  # fmt: skip
    p = Parser(aliasse)
    assert p.parse("FUNKTION=X,SH45").paare == [("W_FUNKTION", "X"), ("W_SITZHOEHE", "45")]
    assert p.parse("FUNK=X_46").paare == [("W_FUNKTION", "X"), ("W_SITZHOEHE", "46")]
    assert Parser(seed_regelstand().alias_liste()).parse("FUNK=X_46").paare == [("FUNKTION", "X"), ("SITZHOEHE", "46")]


# ---------------------------------------------------------------------------------------------------------
# Laden (Fixture im echten Format) und Versionen


@pytest.fixture(scope="module")
def erg():
    return loader.lade_fixtures()


@pytest.fixture(scope="module")
def src(erg):
    return SapSource.from_ladeergebnis(erg)


def test_cukn_header_und_filter(erg):
    p = erg.protokoll["CUKN"]
    assert p.header["Datenblock für Wissensablage"] == "KNBLK" and p.header["int. Zähler"] == "ADZHL"
    assert p.header["BIN2-Datenelement fuer SYST"] == "LAENGE" and not p.unbekannte_spalten
    assert set(erg.tabellen["CUKN"]["KNNUM"]) <= erg.schluessel["W"]


def test_cukn_versionen_und_bloecke(src):
    t = src.texte
    assert t["501"] == "$PARENT.SITZQUALI = 'HR'."  # Version der CUKB (ADZHL 2), nicht die neuere ADZHL 3
    assert "531" not in t  # gültige Version gelöscht → kein Text, Rückfall auf den Namen
    assert t["504"] == "$PARENT.FUNKTION = 'X' AND $PARENT.SITZQUALI = 'HR' and $parent.ELEKTRO = 'X'."  # 2 Blöcke
    assert t["506"] == "$PARENT.SITZQUALI = 'HR'"  # Kommentarzeile entfernt
    assert src.beziehungen["547"]["text"] is None and src.beziehungen["540"]["text"].startswith("$parent.W_RUECK")
    a = src.quelltext_abdeckung()
    assert a["cukn"] and a["mit_text"] == 17 and a["ohne_text"] == 7 and "547 FUNK=X" in a["ohne_beispiele"]


def test_ohne_cukn_wie_bisher(erg):
    tabs = {k: v for k, v in erg.tabellen.items() if k != "CUKN"}
    s = SapSource(tabs, erg.export_daten)
    assert "cukn_fehlt" in s.marker and any("CUKN" in w for w in s.warnungen)
    assert all(b["text"] is None for b in s.beziehungen.values())
    zeilen = Aufloeser(s, seed_regelstand()).loese_alle(["90000007"]).zeilen
    z = next(z for z in zeilen if z["posnr"] == "0010")
    assert z["spur"]["beziehungen"][0]["quelle"] == "name"
    assert z["spur"]["beziehungen"][0]["paare"] == [("RUECKEN_FUNK", "X"), ("FUNKTION", "X")]


def test_cukn_aus_xlsx_mit_auffuellung(tmp_path):
    """Echtes Dateiformat: XLSX mit Kleinbuchstaben-Endung, SE16-Header, Zeilen auf 72 aufgefüllt."""
    p = tmp_path / "EXPORT_CUKN_20261013_084659.xlsx"
    daten = blk("$PARENT.W_FUNKTION = 'VZMO'", "AND", "$PARENT.W_SITZHOEHE = '45'.")
    pd.DataFrame({"Interne Nummer des Wissensbausteins": ["0000000542"], "int. Zähler": ["0"],
                  "Blockzähler Wissensbaustein": ["0"], "Löschkennzeichen": [""], "Änderungsnummer": [""],
                  "Gültig ab": [""], "Gültig bis": ["9999-12-31"], "BIN2-Datenelement fuer SYST": [len(daten)],
                  "Datenblock für Wissensablage": [daten]}).to_excel(p, index=False)  # fmt: skip
    assert loader.verzeichnis_quellen(tmp_path)["CUKN"].pfad == p  # Name ohne Rücksicht auf Groß/klein
    quellen = loader.fixture_quellen(loader.config.FIXTURES_DIR)
    quellen["CUKN"] = loader.Quelle("CUKN", p, loader.export_datum_aus_name(p.name))
    e = loader.lade_quellen(quellen)
    s = SapSource(e.tabellen, {"STPO": e.export_daten["STPO"]})
    assert s.texte == {"542": "$PARENT.W_FUNKTION = 'VZMO' AND $PARENT.W_SITZHOEHE = '45'."}


# ---------------------------------------------------------------------------------------------------------
# Auflösung mit Quelltext (Root 90000007) und Spur


def test_aufloesung_mit_quelltext(src):
    zeilen = {z["posnr"]: z for z in Aufloeser(src, seed_regelstand()).loese_alle(["90000007"]).zeilen}
    # SAP-Merkmale haben vor der Umschlüsselung keine Regeln → kein Rang (D4)
    assert zeilen["0010"]["status"] == "manuell_prüfen" and "kein_rang_fuer:W_FUNKTION" in zeilen["0010"]["grund"]
    assert zeilen["0020"]["grund"].endswith("W_SITZHOEHE=47 ≠ gewählt 45")  # D3 auch für W_SITZHOEHE
    assert zeilen["0040"]["grund"].startswith("nicht parsbar: PP2000_KLIPS_CNC<>X (specified")  # D11
    assert zeilen["0050"]["grund"] == "kein_rang_fuer:SCH_ART"  # aus Text keine Systemregel
    assert zeilen["0070"]["status"] == "basis"  # Rückfall auf den Namen FUNK=X
    assert zeilen["0090"]["status"] == "unbedingt"  # Prozedur mit Quelltext wird ignoriert (D10)
    b = zeilen["0010"]["spur"]["beziehungen"][0]
    assert b["quelle"] == "text" and b["text"].startswith("$parent.W_RUECKENVERST ='X' and")
    assert b["knnam"] == "RUECKEN_FUNK=X,FUNKTION=X"
    rueckfall = zeilen["0070"]["spur"]["beziehungen"][0]
    assert (rueckfall["knnam"], rueckfall["text"], rueckfall["quelle"]) == ("FUNK=X", None, "name")
