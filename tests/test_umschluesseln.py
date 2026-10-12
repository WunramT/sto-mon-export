"""`basis-bom regel umschluesseln`: Zuordnung Legacy-Merkmal → SAP-Merkmal aus Name ↔ Quelltext, Ausführung (D21)."""

import pytest
import sqlalchemy as sa
from typer.testing import CliRunner

from basis_bom import loader, rules
from basis_bom import umschluesseln as um
from basis_bom.cli import app
from basis_bom.explode import Aufloeser
from basis_bom.source import SapSource


def test_paare_zuordnen():
    paare, rest_n, rest_t = um.paare_zuordnen([("RUECKEN_FUNK", "STLR"), ("SITZHOEHE", "47")],
                                              [("W_RUECKENVERST", "STLR"), ("W_SITZHOEHE", "47")])  # fmt: skip
    assert paare == [("RUECKEN_FUNK", "W_RUECKENVERST", "STLR", False), ("SITZHOEHE", "W_SITZHOEHE", "47", False)]
    # gleicher Wert mehrfach: über die Reihenfolge, gekennzeichnet
    paare, _, _ = um.paare_zuordnen([("RUECKEN_FUNK", "X"), ("FUNKTION", "X")],
                                    [("W_RUECKENVERST", "X"), ("W_FUNKTION", "X")])  # fmt: skip
    assert paare == [("RUECKEN_FUNK", "W_RUECKENVERST", "X", True), ("FUNKTION", "W_FUNKTION", "X", True)]
    # Multi-Wert und Negation zählen als Wertmenge; Unpassendes bleibt übrig
    paare, rest_n, rest_t = um.paare_zuordnen([("A", "X/Y"), ("B", "≠Z"), ("C", "1")], [("W_A", "Y/X"), ("W_B", "≠Z"),
                                                                                       ("W_C", "2")])  # fmt: skip
    assert [(a, n) for a, n, _, _ in paare] == [("A", "W_A"), ("B", "W_B")]
    assert rest_n == [("C", "1")] and rest_t == [("W_C", "2")]


@pytest.fixture(scope="module")
def vorschau():
    src = SapSource.from_ladeergebnis(loader.lade_fixtures())
    return um.leite_ab(src, rules.seed_regelstand())


def test_vorschau_aus_fixtures(vorschau):
    v = vorschau
    assert v.zuordnung == {"ARM_L": "W_ARM_L", "RUECKEN_FUNK": "W_RUECKENVERST", "SITZHOEHE": "W_SITZHOEHE"}
    assert [b.knnum for b in v.belege["SITZHOEHE"]["W_SITZHOEHE"]] == ["541", "542", "546"]  # SH45 → SITZHOEHE
    assert [b.reihenfolge for b in v.belege["RUECKEN_FUNK"]["W_RUECKENVERST"]] == [True, False]
    # FUNKTION heißt in den Fixture-Texten teils FUNKTION, teils W_FUNKTION → nicht vorgeschlagen
    assert v.mehrdeutig == {"FUNKTION": {"FUNKTION": 4, "W_FUNKTION": 4}}
    assert v.gleich == {"ELEKTRO": 1, "SITZQUALI": 6}
    assert [s["knnum"] for s in v.systemregeln] == ["544"]  # PP4000_PIANKA_T25_WYBOR → SCH_ART
    text = um.vorschau_text(v, rules.seed_regelstand(), manuell={"FUNKTION": "W_FUNKTION"})
    assert "RUECKEN_FUNK → W_RUECKENVERST  (2 Belege, davon 1 über die Reihenfolge)" in text
    assert "Regeln: X BASIS 1, ST BASIS 2, KV OFFEN" in text and "FUNKTION → W_FUNKTION  (manuell" in text
    assert "17 von 24 Auswahlbedingungen mit Text" in text


def test_lies_zuordnung():
    assert um.lies_zuordnung(["funktion = W_FUNKTION", "A=B"]) == {"FUNKTION": "W_FUNKTION", "A": "B"}
    with pytest.raises(ValueError):
        um.lies_zuordnung(["FUNKTION"])


# ---------------------------------------------------------------------------------------------------------
# Ausführen gegen die Fixture-Datenbank (Stand danach exakt wiederherstellen)


@pytest.fixture()
def stand_sichern(fixture_db):
    with fixture_db.begin() as con:
        max_id = {t: con.execute(sa.text(f"SELECT coalesce(max(id), 0) FROM basis_bom.{t}")).scalar()
                  for t in ("regel", "alias")}  # fmt: skip
        t0 = con.execute(sa.text("SELECT clock_timestamp()")).scalar()
        namen = con.execute(sa.text("SELECT merkmal, text FROM basis_bom.merkmal_text")).all()
    yield
    with fixture_db.begin() as con:
        for t, i in max_id.items():
            con.execute(sa.text(f"DELETE FROM basis_bom.{t} WHERE id > :i"), {"i": i})
            con.execute(sa.text(f"UPDATE basis_bom.{t} SET gueltig_bis = NULL WHERE gueltig_bis >= :t"), {"t": t0})
        con.execute(sa.text("DELETE FROM basis_bom.merkmal_text"))
        for m, x in namen:
            con.execute(sa.text("INSERT INTO basis_bom.merkmal_text (merkmal, text) VALUES (:m, :x)"), {"m": m, "x": x})


def _cli(fixture_db, monkeypatch, *args):
    monkeypatch.setenv("DATABASE_URL", fixture_db.url.render_as_string(hide_password=False))
    res = CliRunner().invoke(app, ["regel", "umschluesseln", *args])
    assert res.exit_code == 0, res.output
    return res.output


def test_cli_vorschau_aendert_nichts(fixture_db, monkeypatch, stand_sichern):
    vorher = rules.lade_regelstand(fixture_db)
    out = _cli(fixture_db, monkeypatch)
    assert "SITZHOEHE → W_SITZHOEHE  (3 Belege)" in out and "Mehrdeutig" in out and "Nur Vorschau" in out
    assert rules.lade_regelstand(fixture_db).regeln == vorher.regeln


def test_cli_ausfuehren(fixture_db, monkeypatch, stand_sichern):
    out = _cli(fixture_db, monkeypatch, "--ausfuehren", "--zuordnung", "FUNKTION=W_FUNKTION", "--von", "Test")
    assert "10 Regeln, 16 Kürzel, 4 Anzeigenamen; 0 Konflikte" in out
    rs = rules.lade_regelstand(fixture_db)
    assert rs.regel("W_FUNKTION", "MANUEL") == rules.Regel("W_FUNKTION", "MANUEL", "BASIS", 2)
    assert rs.regel("FUNKTION", "MANUEL") is None and rs.regel("W_RUECKENVERST", "X").rang == 1
    assert rs.aliasse["FUNK"].merkmal == "W_FUNKTION" and rs.aliasse["SH"].merkmal == "W_SITZHOEHE"
    assert rs.aliasse["W_FUNKTION"] == rules.Alias("W_FUNKTION", "W_FUNKTION", "BASIS")
    with fixture_db.connect() as con:
        r = con.execute(sa.text("SELECT begruendung, geaendert_von FROM basis_bom.regel WHERE merkmal = 'W_FUNKTION' "
                                "AND wert = 'X' AND gueltig_bis IS NULL")).one()  # fmt: skip
        alt = con.execute(sa.text("SELECT count(*) FROM basis_bom.regel WHERE merkmal = 'FUNKTION' "
                                  "AND gueltig_bis IS NOT NULL")).scalar()  # fmt: skip
        namen = dict(con.execute(sa.text("SELECT merkmal, text FROM basis_bom.merkmal_text")).all())
    assert r.begruendung.startswith(um.BEGRUENDUNG) and r.geaendert_von == "Test"
    assert alt == 5  # historisiert (D21), nicht gelöscht
    assert namen["W_RUECKENVERST"] == "Rückenfunktion" and namen["W_SITZHOEHE"] == "Sitzhöhe"
    # db init (Seeds) bringt die umgeschlüsselten Legacy-Regeln nicht zurück
    from basis_bom import db

    db.init_schema(fixture_db)
    assert rules.lade_regelstand(fixture_db).regel("FUNKTION", "X") is None
    # Root mit Quelltext: Text (W_*) und Rückfall über Kürzel (FUNK=X → W_FUNKTION) passen zusammen
    zeilen = {z["posnr"]: z for z in Aufloeser(SapSource.from_db(fixture_db), rules.lade_regelstand(fixture_db))
              .loese_alle(["90000007"]).zeilen}  # fmt: skip
    assert {p: zeilen[p]["status"] for p in ("0010", "0020", "0030", "0060", "0070", "0080")} == {
        "0010": "basis", "0020": "ausgeschlossen", "0030": "ausgeschlossen", "0060": "basis", "0070": "basis",
        "0080": "ausgeschlossen"}  # fmt: skip
    assert zeilen["0070"]["spur"]["beziehungen"][0]["paare"] == [("W_FUNKTION", "X")]


def test_konflikte_und_offen_ziel(fixture_db, stand_sichern):
    rules.setze_regel(fixture_db, "W_FUNKTION", "X", "NICHT_BASIS", geaendert_von="test")  # Entscheidung → Konflikt
    rules.trage_offen_ein(fixture_db, [("W_FUNKTION", "MANUEL")], "test")  # beobachtet OFFEN → wird ersetzt
    rules.setze_regel(fixture_db, "W_RUECKENVERST", "STLR", "BASIS", 1, geaendert_von="test")  # Rang 1 belegt
    b = um.fuehre_aus(fixture_db, {"FUNKTION": "W_FUNKTION", "RUECKEN_FUNK": "W_RUECKENVERST", "A": "B", "B": "C"})
    assert any(k.startswith("FUNKTION=X (BASIS 1): Zielregel W_FUNKTION=X existiert schon") for k in b.konflikte)
    assert any(k.startswith("RUECKEN_FUNK=X (BASIS 1): Rang 1 ist in W_RUECKENVERST schon mit STLR") for k in b.konflikte)
    assert any("Kette" in k for k in b.konflikte)
    rs = rules.lade_regelstand(fixture_db)
    assert rs.regel("FUNKTION", "X").status == "BASIS"  # übersprungen, bleibt
    assert rs.regel("W_FUNKTION", "X").status == "NICHT_BASIS"
    assert rs.regel("W_FUNKTION", "MANUEL") == rules.Regel("W_FUNKTION", "MANUEL", "BASIS", 2)
    assert rs.regel("W_RUECKENVERST", "ST").rang == 2 and rs.regel("RUECKEN_FUNK", "X") is not None
