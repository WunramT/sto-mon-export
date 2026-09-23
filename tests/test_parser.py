"""Phase 4: Parser. Testfälle aus legacy/basis_bom_v0.py (`test_cases`) plus Sonderfälle."""

import pytest

from basis_bom.parser import Parser
from basis_bom.rules import Alias, seed_regelstand


@pytest.fixture(scope="module")
def parser():
    return Parser(seed_regelstand().alias_liste())


LEGACY = [
    ("SITZQUALI=HR", [("SITZQUALI", "HR")]),
    ("SITZQUALI=HR_SITZHOEHE=46", [("SITZQUALI", "HR"), ("SITZHOEHE", "46")]),
    ("ARM_L=X_ARM_OPTIK=1_FUNK=WA", [("ARM_L", "X"), ("ARM_OPTIK", "1"), ("FUNKTION", "WA")]),
    ("RUECKEN_FUNK=STLR,SITZHOEHE=47", [("RUECKEN_FUNK", "STLR"), ("SITZHOEHE", "47")]),
    ("FUNK=X_SIQUALI=HR_ELEKTRO=X", [("FUNKTION", "X"), ("SITZQUALI", "HR"), ("ELEKTRO", "X")]),
    ("ARM_OPTIK=1_SITZQ_HR", [("ARM_OPTIK", "1"), ("SITZQUALI", "HR")]),
    ("FUNKTION MANUEL", [("FUNKTION", "MANUEL")]),
    ("SITZQUALI=BS/FK", [("SITZQUALI", "BS/FK")]),
    ("ARM_L=X_ARM_OPTIK=2_45", [("ARM_L", "X"), ("ARM_OPTIK", "2"), ("SITZHOEHE", "45")]),
    # Legacy lieferte ELEKTRO='FAL_SH48'; SH48 ist Sitzhöhe 48 (docs/FRAGEN.md Q13)
    ("ELEKTRO=FAL_SH48_SQ=HR", [("ELEKTRO", "FAL"), ("SITZHOEHE", "48"), ("SITZQUALI", "HR")]),
    ("FUNK=X_SIQUALI=FK/BS_E=FALMR", [("FUNKTION", "X"), ("SITZQUALI", "FK/BS"), ("ELEKTRO", "FALMR")]),
    ("RUECK=X_FUNK=X,SITZHOEHE=47", [("RUECKEN_FUNK", "X"), ("FUNKTION", "X"), ("SITZHOEHE", "47")]),
]


@pytest.mark.parametrize(("roh", "paare"), LEGACY)
def test_legacy_faelle(parser, roh, paare):
    e = parser.parse(roh)
    assert e.parsbar and not e.systemregel and not e.unbekannte_aliasse and not e.offene_aliasse
    assert e.paare == paare
    assert e.roh == roh


def test_systemregel_kandidat(parser):
    for roh in ("PP4000_KS_VERERBEN", "FUNK_RUECK_ZE", "12345"):
        e = parser.parse(roh)
        assert e.systemregel and e.parsbar and e.paare == [(roh, "vorhanden")]


def test_unbekanntes_kuerzel(parser):
    e = parser.parse("SQ=HR_ZZ=1")
    assert e.parsbar and e.paare == [("SITZQUALI", "HR")] and e.unbekannte_aliasse == ["ZZ"]
    assert parser.parse("ZZ=1").klasse == "unbekannter_alias"


def test_optik_ohne_suffix(parser):
    e = parser.parse("OPTIK=A")
    assert e.parsbar and e.paare == [] and e.offene_aliasse == ["OPTIK"]
    assert parser.parse("ARM=2").offene_aliasse == ["ARM"]


@pytest.mark.parametrize("roh", ["SQ<>HR", "SQ!=HR", "NICHT SQ=HR", "SITZQUALI NOT HR"])
def test_negation_nicht_parsbar(parser, roh):
    e = parser.parse(roh)
    assert not e.parsbar and e.fehler.startswith("negation") and e.paare == []


@pytest.mark.parametrize("roh", ["", "SQ=", "SQ=HR SH=46", "=HR"])
def test_nicht_parsbar(parser, roh):
    assert not parser.parse(roh).parsbar


def test_leerzeichen_um_gleich_und_kleinschreibung(parser):
    assert parser.parse("sitzquali = hr").paare == [("SITZQUALI", "HR")]


def test_multiwert_bleibt_ungeteilt(parser):
    assert parser.parse("SQ=HR/XX").paare == [("SITZQUALI", "HR/XX")]
    assert parser.parse("SQ=FK+BS").paare == [("SITZQUALI", "FK+BS")]


def test_aliasse_aus_tabelle_laengste_zuerst():
    p = Parser([Alias("S", "SITZQUALI", "BASIS"), Alias("SQX", "SITZTIEFE", "BASIS")])
    assert p.parse("SQX=1").paare == [("SITZTIEFE", "1")]
    assert p.parse("S=HR").paare == [("SITZQUALI", "HR")]
    # Nicht-BASIS-Alias wird nicht verwendet
    assert Parser([Alias("SQ", "SITZQUALI", "OFFEN")]).parse("SQ=HR").offene_aliasse == ["SQ"]
