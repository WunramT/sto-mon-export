"""Phase 5: Ranking pro Ebene (D1–D5)."""

from basis_bom.ranking import MANUELL, PASST, PASST_NICHT, einzelwerte, pruefe_paar, waehle
from basis_bom.rules import Regel, Regelstand, seed_regelstand

RS = Regelstand.aus_listen(
    [
        Regel("FUNKTION", "X", "BASIS", 1),
        Regel("FUNKTION", "MANUEL", "BASIS", 2),
        Regel("FUNKTION", "WA", "NICHT_BASIS"),
        Regel("SITZQUALI", "HR", "BASIS", 1),
        Regel("SITZQUALI", "FK", "BASIS", 2),
        Regel("SITZQUALI", "BS", "NICHT_BASIS"),
        Regel("MOTOR", "M1", "NICHT_BASIS"),
        Regel("MOTOR", "M2", "OFFEN"),
    ]
)


def test_x_schlaegt_manuel():
    wahl = waehle([("FUNKTION", "MANUEL"), ("FUNKTION", "X")], RS)
    assert wahl.gewaehlt == {"FUNKTION": "X"} and wahl.marker == []
    assert pruefe_paar("FUNKTION", "MANUEL", wahl, RS).ergebnis == PASST_NICHT
    assert pruefe_paar("FUNKTION", "X", wahl, RS).ergebnis == PASST


def test_nur_manuel_vorhanden():
    wahl = waehle([("FUNKTION", "MANUEL"), ("FUNKTION", "WA")], RS)
    assert wahl.gewaehlt == {"FUNKTION": "MANUEL"}


def test_nur_nicht_basis_marker():
    wahl = waehle([("MOTOR", "M1"), ("MOTOR", "M2")], RS)
    assert wahl.gewaehlt == {} and wahl.marker == ["kein_rang_fuer:MOTOR"]
    p = pruefe_paar("MOTOR", "M1", wahl, RS)
    assert p.ergebnis == MANUELL and p.grund == "kein_rang_fuer:MOTOR"


def test_multiwert_bs_fk_bei_gewaehltem_fk():
    wahl = waehle([("SITZQUALI", "BS/FK"), ("SITZQUALI", "BS")], RS)
    assert wahl.gewaehlt == {"SITZQUALI": "FK"}
    assert pruefe_paar("SITZQUALI", "BS/FK", wahl, RS).ergebnis == PASST
    assert pruefe_paar("SITZQUALI", "FK+BS", wahl, RS).ergebnis == PASST
    assert pruefe_paar("SITZQUALI", "BS", wahl, RS).ergebnis == PASST_NICHT


def test_multiwert_mit_unbekanntem_teilwert():
    wahl = waehle([("SITZQUALI", "HR/XX")], RS)
    assert wahl.gewaehlt == {"SITZQUALI": "HR"} and wahl.marker == ["offen_neben_rang:SITZQUALI"]
    p = pruefe_paar("SITZQUALI", "HR/XX", wahl, RS)
    assert p.ergebnis == MANUELL and "XX" in p.grund


def test_zwei_ebenen_unterschiedliche_wahl():
    oben = waehle([("SITZQUALI", "HR"), ("SITZQUALI", "FK")], RS)
    unten = waehle([("SITZQUALI", "FK"), ("SITZQUALI", "BS")], RS)
    assert oben.gewaehlt["SITZQUALI"] == "HR" and unten.gewaehlt["SITZQUALI"] == "FK"
    assert pruefe_paar("SITZQUALI", "FK", oben, RS).ergebnis == PASST_NICHT
    assert pruefe_paar("SITZQUALI", "FK", unten, RS).ergebnis == PASST


def test_sitzhoehe_numerisch():
    wahl = waehle([("SITZHOEHE", "48"), ("SITZHOEHE", "100"), ("SITZHOEHE", "46")], RS)
    assert wahl.gewaehlt == {"SITZHOEHE": "46"}
    assert pruefe_paar("SITZHOEHE", "46", wahl, RS).ergebnis == PASST
    assert pruefe_paar("SITZHOEHE", "48", wahl, RS).ergebnis == PASST_NICHT
    assert pruefe_paar("SITZHOEHE", "46/48", wahl, RS).ergebnis == PASST


def test_sitzhoehe_nicht_numerisch():
    wahl = waehle([("SITZHOEHE", "HOCH")], RS)
    assert wahl.marker == ["kein_rang_fuer:SITZHOEHE"]


def test_offener_wert_neben_rang_sichtbar():
    wahl = waehle([("SITZQUALI", "HR"), ("SITZQUALI", "ZZ")], RS)
    assert wahl.gewaehlt == {"SITZQUALI": "HR"} and "offen_neben_rang:SITZQUALI" in wahl.marker
    p = pruefe_paar("SITZQUALI", "ZZ", wahl, RS)
    assert p.ergebnis == PASST_NICHT and "OFFEN" in p.grund


def test_systemregel_pseudomerkmal():
    rs = Regelstand.aus_listen([Regel("PP4000_KS_VERERBEN", "vorhanden", "BASIS", 1)])
    wahl = waehle([("PP4000_KS_VERERBEN", "vorhanden")], rs)
    assert pruefe_paar("PP4000_KS_VERERBEN", "vorhanden", wahl, rs).ergebnis == PASST
    offen = waehle([("FUNK_RUECK_ZE", "vorhanden")], rs)
    assert offen.marker == ["kein_rang_fuer:FUNK_RUECK_ZE"]


def test_einzelwerte_und_seeds():
    assert einzelwerte("FK+BS") == ["FK", "BS"] and einzelwerte("HR") == ["HR"]
    wahl = waehle([("FUNKTION", "BK"), ("FUNKTION", "MANUEL")], seed_regelstand())
    assert wahl.gewaehlt == {"FUNKTION": "MANUEL"}
