"""Phase 6: Auflösung auf dem Fixture-Root 90000001 (Golden-File) und Einzelfälle.

Golden-Dateien neu schreiben: `BASIS_BOM_GOLDEN_UPDATE=1 pytest tests/test_explode.py` – danach den Diff prüfen.
"""

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from basis_bom import loader
from basis_bom.explode import Aufloeser, Optionen
from basis_bom.rules import seed_regelstand
from basis_bom.source import SapSource

GOLDEN = Path(__file__).parent / "golden"
ROOT = "90000001"


@pytest.fixture(scope="module")
def erg_laden():
    return loader.lade_fixtures()


@pytest.fixture(scope="module")
def ergebnis(erg_laden):
    src = SapSource.from_ladeergebnis(erg_laden)
    return Aufloeser(src, seed_regelstand()).loese_alle(
        erg_laden.roots["matnr"], erg_laden.root_ausschluss["matnr"]
    )


@pytest.fixture(scope="module")
def df(ergebnis):
    return ergebnis.df().set_index("pfad")


def _golden(name: str, inhalt: str) -> None:
    pfad = GOLDEN / name
    if os.environ.get("BASIS_BOM_GOLDEN_UPDATE") == "1":
        pfad.write_text(inhalt, encoding="utf-8")
    assert pfad.read_text(encoding="utf-8") == inhalt, f"Abweichung zu {pfad}"


def test_golden_aufloesung(ergebnis):
    d = ergebnis.df()
    d["spur"] = d["spur"].map(lambda s: json.dumps(s, ensure_ascii=False, sort_keys=True))
    _golden("aufloesung_fixture.csv", d.to_csv(index=False, sep=";", lineterminator="\n"))
    m = pd.DataFrame(ergebnis.ebene_marker)
    _golden("ebene_marker_fixture.csv", m.to_csv(index=False, sep=";", lineterminator="\n"))


def test_roots_uebersprungen(ergebnis):
    gruende = {u["matnr"]: u["grund"] for u in ergebnis.uebersprungen}
    assert gruende["90000004"] == "root_ausschluss"  # D22
    assert gruende["90000003"].startswith("D15")  # D15
    assert "KZKFG" in gruende["90000002"]  # Stammdatenprüfung D22
    assert set(ergebnis.df()["root_matnr"]) == {ROOT}


def _zeile(df, pfad_ende):
    treffer = df[df.index.str.endswith(pfad_ende)]
    assert len(treffer) == 1, pfad_ende
    return treffer.iloc[0]


def test_drei_ebenen_und_menge_kum(df):
    assert df["ebene"].max() == 3
    assert _zeile(df, "0010:10000101")["menge_kum"] == 2.0  # 1 · 4 / BMENG 2 (D17)
    z = _zeile(df, "0030:10000011/0010:10000111")
    assert z["ebene"] == 3 and z["menge_kum"] == 1.5  # 0,5 · 3 / 1 (BMENG angenommen)
    assert _zeile(df, "90000001/0020:10000002")["menge"] == 2.0  # neueste STPO-Version


def test_ausgeschlossene_baugruppe_vererbt(df):
    assert _zeile(df, "90000001/0030:10000003")["status"] == "ausgeschlossen"
    assert _zeile(df, "0030:10000003/0010:10000301")["status"] == "ausgeschlossen_vererbt"  # D12


def test_manuelle_baugruppe(df):
    assert _zeile(df, "90000001/0060:10000006")["status"] == "manuell_prüfen"  # unbekanntes Kürzel (D6)
    assert _zeile(df, "0060:10000006/0010:10000201")["status"] == "unterhalb_manuell"  # D12
    assert _zeile(df, "0060:10000006/0020:10000202")["status"] == "unterhalb_manuell"
    assert _zeile(df, "0060:10000006/0030:10000203")["status"] == "ausgeschlossen"


def test_prozedur_klasse_ignoriert(df):
    z = _zeile(df, "90000001/0070:10000007")
    assert z["status"] == "basis" and z["spur"]["prozeduren"] == ["PP_PREISFINDUNG"]  # D10
    assert _zeile(df, "90000001/0080:")["status"] == "manuell_prüfen"  # Klassenposition D13
    assert _zeile(df, "90000001/0090:")["status"] == "ignoriert"  # D13


def test_und_logik_ranking_sitzhoehe(df):
    assert _zeile(df, "90000001/0100:10000010")["status"] == "ausgeschlossen"  # D9
    assert _zeile(df, "90000001/0040:10000004")["status"] == "ausgeschlossen"  # X schlägt MANUEL
    assert _zeile(df, "0010:10000001/0010:10000101")["status"] == "basis"  # nur MANUEL auf Ebene 2 (D2)
    assert _zeile(df, "90000001/0120:10000012")["status"] == "basis"  # SH 46 < 48 (D3)
    assert _zeile(df, "90000001/0130:10000013")["status"] == "ausgeschlossen"
    assert _zeile(df, "0010:10000001/0020:10000102")["grund"] == "kein_rang_fuer:SITZQUALI"  # D4


def test_nicht_parsbar_und_multiwert(df):
    assert _zeile(df, "90000001/0140:10000014")["status"] == "manuell_prüfen"  # D11
    assert "XX" in _zeile(df, "90000001/0150:10000015")["grund"]  # D5
    assert _zeile(df, "90000001/0160:10000016")["status"] == "manuell_prüfen"  # Systemregel OFFEN (D7)


def test_eine_zeile_pro_vorkommen(df):
    assert (df["matnr"] == "10000020").sum() == 2  # D16
    assert not df.index.duplicated().any()


def test_spur(df):
    s = _zeile(df, "90000001/0050:10000005")["spur"]
    assert s["gewaehlt"] == {"ELEKTRO": "X", "FUNKTION": "X", "SITZQUALI": "HR"}  # D18
    assert s["beziehungen"][0]["paare"] == [("FUNKTION", "X"), ("SITZQUALI", "HR"), ("ELEKTRO", "X")]
    assert s["status"] == "basis" and "regel_version" in s


def test_zyklus_und_d15_baugruppe(erg_laden):
    tabs = {k: v.copy() for k, v in erg_laden.tabellen.items()}
    mast = tabs["MAST"]
    zusatz = pd.DataFrame(
        [
            {**mast.iloc[0].to_dict(), "MATNR": "10000111", "STLNR": "1000"},  # Zyklus: 10000111 → 1000 → …
            {**mast.iloc[0].to_dict(), "MATNR": "10000020", "STLNR": "1005", "LKENZ": ""},  # D15 bei 10000020
            {**mast.iloc[0].to_dict(), "MATNR": "10000020", "STLNR": "1008", "LKENZ": ""},
        ]  # fmt: skip
    )
    tabs["MAST"] = pd.concat([mast, zusatz], ignore_index=True)
    src = SapSource(tabs, erg_laden.export_daten)
    d = Aufloeser(src, seed_regelstand(), Optionen(max_tiefe=10)).loese_alle([ROOT]).df().set_index("pfad")
    zyklus = d[d["grund"] == "Zyklus im Pfad"]
    assert len(zyklus) == 1 and zyklus.iloc[0]["matnr"] == "10000001" and zyklus.iloc[0]["ebene"] == 4
    assert zyklus.iloc[0]["status"] == "manuell_prüfen"
    assert d["ebene"].max() == 5  # andere Baugruppen unter der wiederholten Stückliste 1000
    assert (d.loc[d["matnr"] == "10000020", "grund"].str.startswith("D15")).all()
