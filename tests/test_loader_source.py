"""Phase 2: Loader (Header, Normalisierung, Filter beim Laden) und D14-Gültigkeit in source.py."""

import datetime as dt

import pandas as pd
import pytest

from basis_bom import loader, pruefpunkte
from basis_bom.source import SapSource, StichtagFehler

STICHTAG = dt.date(2026, 9, 23)


@pytest.fixture(scope="module")
def erg():
    return loader.lade_fixtures()


@pytest.fixture(scope="module")
def src(erg):
    return SapSource.from_ladeergebnis(erg)


def test_header_mapping_beschreibend(erg):
    assert {"KNOBJ", "KNNUM", "KNTAB", "DATUV", "LKENZ"} <= set(erg.tabellen["CUOB"].columns)
    assert {"KNNUM", "ADZHL", "KNNAM", "KNART", "KNSTA"} <= set(erg.tabellen["CUKB"].columns)
    assert erg.protokoll["CUKB"].unbekannte_spalten == []


def test_unbekannte_spalte_bleibt_erhalten(tmp_path):
    p = tmp_path / "mara_20260923.csv"
    p.write_text("MATNR;MATKL;Irgendwas Neues\n0001;A;x\n", encoding="utf-8")
    prot = loader.Protokoll("MARA", p.name, None)
    df = loader.normalisiere(next(loader.lese_roh(p, prot)), "MARA", prot)
    assert prot.trenner == ";"
    assert "IRGENDWAS_NEUES" in df.columns and prot.unbekannte_spalten == ["IRGENDWAS_NEUES"]
    assert df["MATNR"].tolist() == ["1"]


def test_normalisierung(erg):
    stpo = erg.tabellen["STPO"]
    assert "10000002" in set(stpo["IDNRK"]) and "1000" in set(stpo["STLNR"])
    assert not stpo["STLNR"].str.startswith("0").any()
    assert set(stpo.loc[stpo["STLKN"] == "2", "MENGE"]) == {1.0, 2.0}  # Dezimalkomma
    assert erg.tabellen["STKO"].query("STLNR == '1001'")["BMENG"].tolist() == [1.0, 2.0]
    assert loader.ohne_nullen("11071032.0") == "11071032"
    assert loader.parse_datum("01.02.2026") == dt.date(2026, 2, 1)
    assert loader.parse_datum("00000000") is None


def test_filter_beim_laden(erg):
    assert set(erg.tabellen["MAST"]["WERKS"]) == {"4000"} and set(erg.tabellen["MAST"]["STLAN"]) == {"1"}
    assert "9999" not in set(erg.tabellen["STPO"]["STLNR"])  # STLNR ∉ S
    assert "1009" not in erg.schluessel["S"]  # MAST mit LKENZ
    cuob = erg.tabellen["CUOB"]
    assert set(cuob["KNTAB"]) == {"STPO"} and "999999" not in set(cuob["KNOBJ"])
    assert "888" not in set(erg.tabellen["CUKB"]["KNNUM"])  # KNNUM ∉ W
    assert "99999999" not in set(erg.tabellen["MARA"]["MATNR"])  # MATNR ∉ M
    assert set(erg.tabellen["MAKT"]["SPRAS"]) == {"D"}
    assert set(erg.tabellen["MARC"]["WERKS"]) == {"4000"}
    assert erg.export_daten["STPO"] == STICHTAG


def test_cukb_geloescht_zukuenftig_versioniert(src):
    cukb = src.cukb.set_index("KNNUM")
    assert cukb.loc["501", "KNNAM"] == "SQ=HR"  # ADZHL 2; 3 nicht freigegeben, 4 zukünftig
    assert cukb.loc["501", "ADZHL"] == "2"
    assert "599" not in cukb.index  # gelöscht
    assert len(cukb.index) == len(set(cukb.index))


def test_stpo_gueltigkeit(src):
    pos = src.stpo.query("STLNR == '1000'").set_index("STLKN")
    assert pos.loc["2", "MENGE"] == 2.0  # neueste Version
    assert "17" not in pos.index  # gelöscht
    assert "18" not in pos.index  # DATUV nach Stichtag


def test_stas_und_stko(src):
    assert set(src.positionen_fuer("1001", "1")["STLKN"]) == {
        "1",
        "2",
        "3",
        "4",
    }  # Knoten 5 per STAS gelöscht
    assert set(src.positionen_fuer("1000", "1")["STLKN"]) >= {"1", "2", "16"}  # ohne STAS: alle
    assert src.bmeng("1001", "1") == (2.0, False)
    assert src.bmeng("1004", "1") == (1.0, True)


def test_cuob_geloescht(src):
    assert src.knnum_pro_knobj["100001"] == ["501"]
    assert "100001" in src.knobj_roh


def test_marker_und_d15(src):
    assert "cawn_fehlt" in src.marker and "knart_fehlt" not in src.marker
    assert len(src.stlnr_pro_material["90000003"]) == 2
    assert src.stichtag == STICHTAG


def test_knart_fehlt_marker(erg):
    tabs = dict(erg.tabellen)
    tabs["CUKB"] = tabs["CUKB"].drop(columns=["KNART"])
    assert "knart_fehlt" in SapSource(tabs, erg.export_daten).marker


def test_gemischte_stichtage(erg):
    daten = dict(erg.export_daten, CUKB=dt.date(2026, 5, 12))
    s = SapSource(erg.tabellen, daten, prod=False)
    assert s.stichtag == STICHTAG and s.warnungen
    with pytest.raises(StichtagFehler):
        SapSource(erg.tabellen, daten, prod=True)


def test_root_xlsx(tmp_path):
    p = tmp_path / "planzeiten.xlsx"
    with pd.ExcelWriter(p) as w:
        pd.DataFrame({"Modell": ["A", "B", "C"], "Materialnummer": ["011071032", "11071089", "11071089"],
                      "Zeit": [1, 2, 3]}).to_excel(w, sheet_name="Alle", index=False)  # fmt: skip
        pd.DataFrame({"x": [1]}).to_excel(w, sheet_name="Info", index=False)
    df, info = loader.lese_root_xlsx(p)
    assert df["matnr"].tolist() == ["11071032", "11071089"]
    assert info["blatt"] == "Alle" and info["duplikate"] == 1 and info["spaltenkopf"] == "Materialnummer"


def test_legacy_material_list():
    lst = loader.legacy_material_list()
    assert len(lst) > 100 and "11071032" in lst


def test_pruefpunkte(erg, tmp_path):
    text = pruefpunkte.berichte(erg)
    assert "1. **CUKB-Spalten**" in text and "8. **Excel-Grenze" in text
    ziel = tmp_path / "FRAGEN.md"
    ziel.write_text("# Fragen\n\nVorher.\n", encoding="utf-8")
    pruefpunkte.schreibe_fragen(text, ziel)
    pruefpunkte.schreibe_fragen(text, ziel)  # idempotent
    inhalt = ziel.read_text(encoding="utf-8")
    assert inhalt.count(pruefpunkte.START) == 1 and "Vorher." in inhalt


def test_db_roundtrip(pg_engine, erg, src):
    from basis_bom import db

    db.init_schema(pg_engine)
    loader.schreibe(pg_engine, erg, quelle_roots="fixtures")
    s = SapSource.from_db(pg_engine)
    assert s.stichtag == STICHTAG
    assert s.cukb.set_index("KNNUM").loc["501", "KNNAM"] == "SQ=HR"
    assert set(s.positionen_fuer("1001", "1")["STLKN"]) == {"1", "2", "3", "4"}
    assert s.bmeng("1001", "1") == (2.0, False)
    assert len(s.stpo) == len(src.stpo)


def _mit_cabn(tmp_path, inhalt: str):
    p = tmp_path / "EXPORT_cabn_20260923_142303.csv"
    p.write_text(inhalt, encoding="utf-8")
    quellen = loader.fixture_quellen(loader.config.FIXTURES_DIR)
    quellen["CABN"] = loader.Quelle("CABN", p, STICHTAG)
    return loader.lade_quellen(quellen)


def test_cabn_beschreibende_header(tmp_path):
    erg = _mit_cabn(tmp_path, "Int. Merkmalsnummer;int. Zähler;Merkmal;Merkmalbezeichnung\n"
                              "0000000123;1;SITZQUALI;Sitzqualität\n0000000124;1;ANDERES;x\n")  # fmt: skip
    cabn = erg.tabellen["CABN"]
    assert cabn["ATINN"].tolist() == ["123"] and cabn["ATNAM"].tolist() == ["SITZQUALI"]
    assert erg.schluessel["A"] == {"123"}


def test_cabn_ohne_atinn_bricht_nicht_ab(tmp_path):
    erg = _mit_cabn(tmp_path, "Merkmal;Irgendwas\nSITZQUALI;1\n")
    assert "A" not in erg.schluessel and len(erg.tabellen["CABN"]) == 1
