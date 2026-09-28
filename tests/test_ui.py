"""Web-Oberfläche: API über FastAPI-TestClient gegen die Fixture-Datenbank."""

import pytest
from fastapi.testclient import TestClient

from basis_bom import regress, rules
from basis_bom.ui.app import erstelle_app

FK_BASIS = {"regeln": [{"merkmal": "SITZQUALI", "wert": "FK", "status": "BASIS", "rang": 2,
                        "vorher": {"status": "OFFEN", "rang": None}}]}  # fmt: skip


@pytest.fixture()
def client(fixture_db):
    return TestClient(erstelle_app(fixture_db))


def test_seite_und_meta(client):
    assert "Basis-Stückliste" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    m = client.get("/api/meta").json()
    assert m["stichtag"] == "2026-09-23" and m["regeln"] > 0


def test_materialien(client):
    ms = {m["matnr"]: m for m in client.get("/api/materialien").json()}
    assert ms["90000001"]["zustand"] in {"offen", "in_arbeit", "bestaetigt"}
    assert ms["90000003"]["zustand"] == "nicht_aufloesbar" and "D15" in ms["90000003"]["grund"]
    assert [m["matnr"] for m in client.get("/api/materialien?q=hocker").json()] == ["90000006"]


def test_material_mit_erklaerung_und_fragen(client):
    d = client.post("/api/material/90000001", json={"entwurf": None}).json()
    pos = {p["matnr"]: p for p in d["positionen"] if p["matnr"]}
    assert pos["10000102"]["status"] == "manuell_prüfen"
    assert pos["10000102"]["fragen"][0] == {"typ": "rang", "merkmal": "SITZQUALI",
                                            "text": "Für SITZQUALI ist noch kein Basiswert festgelegt"}  # fmt: skip
    assert "verlangt SITZQUALI = FK, Basis ist HR" in pos["10000003"]["erklaerung"]
    assert pos["10000006"]["fragen"][0]["typ"] == "kuerzel"
    assert "SITZQUALI" in {m["merkmal"] for m in d["merkmale"]}
    assert d["ebenen"]["1000"]["gewaehlt"]["SITZQUALI"] == "HR"


def test_entwurf_vorschau_und_auswirkung(client):
    d = client.post("/api/material/90000006", json={"entwurf": FK_BASIS}).json()
    p = next(x for x in d["positionen"] if x["matnr"] == "10000102")
    assert p["status"] == "basis" and p["vorher"] == "manuell_prüfen" and d["geaendert"] == 1
    a = client.post("/api/auswirkung", json={"entwurf": FK_BASIS}).json()
    assert {m["matnr"] for m in a["materialien"]} == {"90000001", "90000005", "90000006"}
    assert a["materialien"][0]["wechsel"][0] == {"von": "manuell_prüfen", "nach": "basis", "anzahl": 1}
    # ohne Übernahme bleibt der gespeicherte Stand unverändert
    assert rules.lade_regelstand(client.app.state.dienst.eng).status("SITZQUALI", "FK") == "OFFEN"


def test_uebernehmen_mit_konflikt(client, fixture_db):
    r = client.post("/api/uebernehmen", json={"entwurf": FK_BASIS, "von": "Test", "begruendung": "Test"})
    assert r.status_code == 200, r.text
    assert rules.lade_regelstand(fixture_db).regel("SITZQUALI", "FK") == rules.Regel(
        "SITZQUALI", "FK", "BASIS", 2
    )
    # zweiter Entwurf mit veraltetem „vorher“ → Konflikt, nichts geschrieben
    alt = {"regeln": [{"merkmal": "SITZQUALI", "wert": "FK", "status": "NICHT_BASIS", "rang": None,
                       "vorher": {"status": "OFFEN", "rang": None}}]}  # fmt: skip
    k = client.post("/api/uebernehmen", json={"entwurf": alt, "von": "Andere", "begruendung": None})
    assert k.status_code == 409 and k.json()["konflikte"][0]["jetzt"] == {"status": "BASIS", "rang": 2}
    # doppelter Rang wird abgelehnt
    doppelt = {"regeln": [{"merkmal": "SITZQUALI", "wert": "BS", "status": "BASIS", "rang": 1,
                           "vorher": {"status": "OFFEN", "rang": None}}]}  # fmt: skip
    assert client.post("/api/uebernehmen", json={"entwurf": doppelt, "von": "T"}).status_code == 400
    rules.setze_regel(fixture_db, "SITZQUALI", "FK", "OFFEN", geaendert_von="test")


def test_kuerzel_im_entwurf(client):
    e = {
        "aliasse": [
            {
                "alias": "ZZ",
                "merkmal": "SITZTIEFE",
                "status": "BASIS",
                "vorher": {"merkmal": None, "status": "OFFEN"},
            }
        ]
    }
    d = client.post("/api/material/90000001", json={"entwurf": e}).json()
    p = next(x for x in d["positionen"] if x["matnr"] == "10000006")
    assert p["fragen"] == [
        {"typ": "rang", "merkmal": "SITZTIEFE", "text": "Für SITZTIEFE ist noch kein Basiswert festgelegt"}
    ]


def test_review_bestaetigen_und_regression(client, fixture_db):
    d = client.post("/api/material/90000006", json={"entwurf": None}).json()
    alle = {p["id"]: {"urteil": "richtig"} for p in d["positionen"]}
    teil = dict(list(alle.items())[:1])
    r = client.post("/api/review/90000006", json={"von": "Erika", "urteile": teil})
    assert r.status_code == 200
    assert client.post("/api/bestaetigen/90000006", json={"von": "Erika"}).status_code == 400  # unvollständig
    assert client.post("/api/review/90000006", json={"von": "Erika", "urteile": alle}).status_code == 200
    d2 = client.post("/api/material/90000006", json={"entwurf": None}).json()
    assert len(d2["review"]["urteile"]) == len(alle) and d2["review"]["veraltet"] == 0
    assert client.post("/api/bestaetigen/90000006", json={"von": "Erika"}).json() == {
        "bestaetigt": "90000006"
    }
    zustand = {m["matnr"]: m["zustand"] for m in client.get("/api/materialien").json()}
    assert zustand["90000006"] == "bestaetigt"
    # Regression: Regeländerung → rot; Review zeigt veraltete Zeilen
    lid = client.post("/api/review/90000006", json={"von": "Erika", "urteile": alle}).json()["lauf_id"]
    fixture_db_status = regress.regress(fixture_db, lid)
    assert fixture_db_status.empty
    client.post("/api/bestaetigen/90000006", json={"von": "Erika"})
    client.post("/api/uebernehmen", json={"entwurf": FK_BASIS, "von": "Test"})
    try:
        d3 = client.post("/api/material/90000006", json={"entwurf": None}).json()
        assert d3["review"]["veraltet"] == 1
        from basis_bom import lauf

        lid2, _ = lauf.fuehre_aufloesung_aus(fixture_db, ["90000006"])
        assert not regress.regress(fixture_db, lid2).empty
    finally:
        rules.setze_regel(fixture_db, "SITZQUALI", "FK", "OFFEN", geaendert_von="test")


def test_ergaenzen_und_ungueltig(client):
    d = client.post("/api/material/90000005", json={"entwurf": None}).json()
    ok = client.post("/api/review/90000005", json={"von": "E", "urteile": {},
                     "ergaenzt": [{"parent_pfad": "90000005", "matnr": "10000999", "menge": 2}]})  # fmt: skip
    assert ok.status_code == 200 and ok.json()["ergaenzt"] == 1
    d2 = client.post("/api/material/90000005", json={"entwurf": None}).json()
    assert d2["review"]["ergaenzt"][0]["matnr"] == "10000999"
    bad = client.post(
        "/api/review/90000005",
        json={"von": "E", "urteile": {d["positionen"][0]["id"]: {"urteil": "vielleicht"}}},
    )
    assert bad.status_code == 400
    assert client.post("/api/review/90000005", json={"von": " ", "urteile": {}}).status_code == 400
