"""Phase 3: Schema basis_bom, Seeds, Constraints."""

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from basis_bom import db, rules


def _zaehle(eng):
    with eng.connect() as con:
        return {
            t: con.execute(sa.text(f"SELECT count(*) FROM basis_bom.{t}")).scalar()
            for t in ("regel", "alias", "root_ausschluss")
        }


def test_init_idempotent_und_seeds(pg_engine):
    db.init_schema(pg_engine)
    vorher = _zaehle(pg_engine)
    db.init_schema(pg_engine)
    assert _zaehle(pg_engine) == vorher
    rs = rules.lade_regelstand(pg_engine)
    assert rs.regel("SITZQUALI", "HR") == rules.Regel("SITZQUALI", "HR", "BASIS", 1)
    assert [r.wert for r in rs.rangliste("FUNKTION")] == ["X", "MANUEL", "BK"]
    assert rs.status("FUNKTION", "WA1") == "OFFEN"
    assert rs.aliasse["SQ"] == rules.Alias("SQ", "SITZQUALI", "BASIS")
    assert rs.aliasse["OPTIK"].status == "OFFEN" and rs.aliasse["OPTIK"].merkmal is None
    assert rs.alias_liste()[0].alias in {"RUECKEN_OPTIK"} or len(rs.alias_liste()[0].alias) >= 12
    assert rs.version is not None
    for tab in ("lauf", "aufloesung", "ebene_marker", "review", "bestaetigt", "root_material"):
        assert db.table_exists(pg_engine, "basis_bom", tab)


def test_doppelter_rang_schlaegt_fehl(pg_engine):
    db.init_schema(pg_engine)
    with pytest.raises(IntegrityError), pg_engine.begin() as con:
        con.execute(
            sa.text(
                "INSERT INTO basis_bom.regel (merkmal, wert, status, rang, geaendert_von) "
                "VALUES ('SITZQUALI', 'FK', 'BASIS', 1, 'test')"
            )
        )


def test_basis_ohne_rang_schlaegt_fehl(pg_engine):
    db.init_schema(pg_engine)
    with pytest.raises(IntegrityError), pg_engine.begin() as con:
        con.execute(
            sa.text(
                "INSERT INTO basis_bom.regel (merkmal, wert, status, geaendert_von) "
                "VALUES ('SITZQUALI', 'QQ', 'BASIS', 'test')"
            )
        )


def test_setze_regel_historisiert(pg_engine):
    db.init_schema(pg_engine)
    vorher = rules.lade_regelstand(pg_engine)
    rules.setze_regel(pg_engine, "MOTOR", "M1", "NICHT_BASIS", geaendert_von="test")
    rules.setze_regel(pg_engine, "MOTOR", "M1", "BASIS", rang=1, geaendert_von="test")
    nachher = rules.lade_regelstand(pg_engine)
    assert nachher.regel("MOTOR", "M1") == rules.Regel("MOTOR", "M1", "BASIS", 1)
    assert rules.lade_regelstand(pg_engine, vorher.version).regel("MOTOR", "M1") is None
    assert nachher.version > vorher.version
    with pg_engine.begin() as con:
        n = con.execute(sa.text("SELECT count(*) FROM basis_bom.regel WHERE merkmal = 'MOTOR'")).scalar()
        con.execute(sa.text("DELETE FROM basis_bom.regel WHERE merkmal = 'MOTOR'"))
    assert n == 2


def test_offen_eintragen(pg_engine):
    db.init_schema(pg_engine)
    assert rules.trage_offen_ein(pg_engine, [("SITZQUALI", "ZZTEST"), ("SITZQUALI", "HR")], "test") == 1
    assert rules.trage_offen_ein(pg_engine, [("SITZQUALI", "ZZTEST")], "test") == 0
    assert rules.trage_alias_offen_ein(pg_engine, ["ZZALIAS"], "test") == 1
    with pg_engine.begin() as con:
        con.execute(sa.text("DELETE FROM basis_bom.regel WHERE wert = 'ZZTEST'"))
        con.execute(sa.text("DELETE FROM basis_bom.alias WHERE alias = 'ZZALIAS'"))


def test_aliasse_aus_cabn(pg_engine):
    import pandas as pd

    from basis_bom import loader

    db.init_schema(pg_engine)
    rules.trage_alias_offen_ein(pg_engine, ["PP4000_DUEBEL"], "test")
    loader.schreibe_tabelle(pg_engine, "CABN", pd.DataFrame({"ATINN": ["1", "2", "3"],
                            "ATNAM": ["PP4000_DUEBEL", "SITZQUALI", ""]}), None)  # fmt: skip
    assert rules.aliasse_aus_cabn(pg_engine) >= 1
    rs = rules.lade_regelstand(pg_engine)
    assert rs.aliasse["PP4000_DUEBEL"] == rules.Alias("PP4000_DUEBEL", "PP4000_DUEBEL", "BASIS")
    assert rs.aliasse["SITZQUALI"].status == "BASIS"
    assert rules.aliasse_aus_cabn(pg_engine) == 0  # idempotent
    with pg_engine.begin() as con:
        con.execute(sa.text("DROP TABLE sap_raw.cabn"))


def test_cli_regel(fixture_db, monkeypatch):
    from typer.testing import CliRunner

    from basis_bom.cli import app

    monkeypatch.setenv("DATABASE_URL", fixture_db.url.render_as_string(hide_password=False))
    r = CliRunner()
    assert r.invoke(app, ["regel", "setzen", "MOTOR", "m9", "BASIS", "--rang", "1"]).exit_code == 0
    assert "M9" in r.invoke(app, ["regel", "liste", "MOTOR"]).output
    assert r.invoke(app, ["regel", "setzen", "MOTOR", "M8", "BASIS"]).exit_code != 0  # Rang fehlt
    assert r.invoke(app, ["regel", "alias", "MOT", "MOTOR"]).exit_code == 0
    assert rules.lade_regelstand(fixture_db).aliasse["MOT"].merkmal == "MOTOR"
