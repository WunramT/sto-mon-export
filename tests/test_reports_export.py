"""Phase 7: Export (D19, Golden-File byteweise), Views und Checks. Review/Regression: tests/test_ui.py."""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa

from basis_bom import checks, export, lauf, loader, rules
from basis_bom.explode import Aufloeser
from basis_bom.source import SapSource

GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture(scope="module")
def fixture_src():
    return SapSource.from_ladeergebnis(loader.lade_fixtures())


def test_export_golden(fixture_src, tmp_path):
    erg = Aufloeser(fixture_src, rules.seed_regelstand()).loese_alle(["90000001"])
    pfade = export.exportiere(erg.df(), fixture_src, tmp_path)
    neu = pfade[0].read_bytes()
    golden = GOLDEN / "grundversion_sap_format.csv"
    if os.environ.get("BASIS_BOM_GOLDEN_UPDATE") == "1":
        golden.write_bytes(neu)
    assert neu == golden.read_bytes()
    assert (tmp_path / "90000001" / "90000001_sap_format.csv").read_bytes() == neu
    kopf, root, *pos = neu.decode().splitlines()
    assert kopf == "Werk;Material;ObjektId;Materialkurztext DE;Menge;ME;PTp;Disp.;Warengrp;MArt;SoB"
    assert root.startswith("4000;90000001;;Sessel STO Basis;;;;")
    assert len(pos) == 10  # nur basis/unbedingt


def test_views(fixture_db):
    lauf.fuehre_aufloesung_aus(fixture_db)
    with fixture_db.connect() as con:

        def q(sql):
            return con.execute(sa.text(sql)).mappings().all()

        ursachen = {r["ursache"] for r in q("SELECT * FROM basis_bom.offene_faelle_ursache")}
        assert {"kein_rang", "nicht_parsbar", "klassenposition", "unbekannter_teilwert",
                "ausgeschlossen_neben_offen"} <= ursachen  # fmt: skip
        assert {r["merkmal"] for r in q("SELECT * FROM basis_bom.kein_rang")} >= {
            "SITZQUALI",
            "PP4000_KS_VERERBEN",
        }
        assert q("SELECT * FROM basis_bom.prozeduren")[0]["prozedur"] == "PP_PREISFINDUNG"
        stat = q("SELECT * FROM basis_bom.statistik_lauf LIMIT 1")[0]
        assert stat["basis"] >= 5 and stat["roots_uebersprungen"] == 3
        abdeckung = {
            (r["merkmal"], r["wert"]): r["positionen"] for r in q("SELECT * FROM basis_bom.regel_abdeckung")
        }
        assert abdeckung[("SITZQUALI", "FK")] >= 2 and abdeckung[("FUNKTION", "WA1")] == 0


def test_checks(fixture_db):
    df = checks.pruefe(fixture_db)
    assert len(df) > 10
    assert df.loc[df["pruefung"] == "export: STLNR in STKO", "ok"].item() is False  # 1004 ohne STKO
    assert df.loc[df["datei"] == "regel_002_cabn.sql", "ok"].isna().all()  # CABN fehlt → übersprungen
