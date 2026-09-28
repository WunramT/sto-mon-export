"""Backend-API (backend/app) über FastAPI-TestClient gegen die Fixture-Datenbank."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("SECRET_KEY", "test-secret-key-mindestens-32-zeichen-lang")
os.environ.setdefault("MASTER_PASSWORD_ADMIN", "geheim")
os.environ.setdefault("MODE", "production")

from app.main import create_app  # noqa: E402

from basis_bom import regress, rules  # noqa: E402

FK_BASIS = {"regeln": [{"merkmal": "SITZQUALI", "wert": "FK", "status": "BASIS", "rang": 2,
                        "vorher": {"status": "OFFEN", "rang": None}}]}  # fmt: skip


@pytest.fixture(scope="module")
def app(fixture_db):
    app = create_app(fixture_db, starte_laden=False)
    app.state.datenstand.beim_start()
    return app


@pytest.fixture()
def client(app):
    c = TestClient(app)
    token = c.post("/api/auth/login", json={"passwort": "geheim"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def test_anmeldung(app):
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/api/auth/config").json()["auth_aktiv"] is True
    assert c.get("/api/meta").status_code == 401
    assert c.post("/api/auth/login", json={"passwort": "falsch"}).status_code == 401
    assert c.get("/api/meta", headers={"Authorization": "Bearer kaputt"}).status_code == 401


def test_datenstand_und_export(client):
    d = client.get("/api/datenstand").json()
    assert d["zustand"] == "bereit" and d["quelle"] == "datenbank"
    r = client.get("/api/export/90000001")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.text.lstrip("\ufeff").startswith("Werk;Material;")
    assert client.get("/api/export/90000003").status_code == 400
    # ohne Exporte im Verzeichnis kein Neuladen
    assert client.post("/api/datenstand/neu-laden").status_code == 400


def test_seite_und_meta(client):
    m = client.get("/api/meta").json()
    assert m["stichtag"] == "2026-09-23" and m["regeln"] > 0


def test_materialien(client):
    ms = {m["matnr"]: m for m in client.get("/api/materialien").json()}
    assert ms["90000001"]["zustand"] in {"offen", "in_arbeit", "bestaetigt"}
    assert (
        ms["90000003"]["zustand"] == "nicht_aufloesbar" and "Mehrere Stücklisten" in ms["90000003"]["grund"]
    )
    assert ms["90000002"]["grund"] == "In SAP nicht als konfigurierbares Material gekennzeichnet"
    assert [m["matnr"] for m in client.get("/api/materialien?q=hocker").json()] == ["90000006"]


def test_material_mit_erklaerung_und_fragen(client):
    d = client.post("/api/material/90000001", json={"entwurf": None}).json()
    pos = {p["matnr"]: p for p in d["positionen"] if p["matnr"]}
    assert pos["10000102"]["status"] == "manuell_prüfen"
    assert pos["10000102"]["fragen"][0] == {
        "typ": "rang", "merkmal": "SITZQUALI", "schluessel": "merkmal:SITZQUALI",
        "text": "Sitzqualität: Auf dieser Stückliste kommt nur FK vor – ist FK ein Basiswert?"}  # fmt: skip
    assert (
        pos["10000016"]["fragen"][0]["text"] == "Gilt die technische Regel „PP4000_KS_VERERBEN“ in der Basis?"
    )
    assert "verlangt Sitzqualität = FK, Basis ist HR" in pos["10000003"]["erklaerung"]
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
    assert rules.lade_regelstand(client.app.state.datenstand.eng).status("SITZQUALI", "FK") in (None, "OFFEN")


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
    assert [(f["typ"], f["merkmal"]) for f in p["fragen"]] == [("rang", "SITZTIEFE")]
    assert p["fragen"][0]["text"] == "Sitztiefe: Auf dieser Stückliste kommt nur 1 vor – ist 1 ein Basiswert?"


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


def test_regeln_mit_beobachteten_werten_und_kuerzeln(client):
    d = client.post("/api/regeln?nur_offen=true", json={"entwurf": None}).json()
    sq = next(m for m in d["merkmale"] if m["merkmal"] == "SITZQUALI")
    assert {w["wert"] for w in sq["werte"]} >= {"HR", "FK", "BS", "XX"}
    assert next(w for w in sq["werte"] if w["wert"] == "FK")["stuecklisten"] >= 2
    assert "ZZ" in {k["alias"] for k in d["kuerzel"]}
    vorher = client.get("/api/meta").json()["offen"]
    assert d["offen"] == vorher > 0
    assert d["offen"] == len(d["fragen"])  # eine Liste, eine Zahl
    frage = next(f for f in d["fragen"] if f.get("merkmal") == "SITZQUALI")
    assert "FK" in frage["werte"] and sq["frage"] == frage
    r = client.post("/api/regeln", json={"entwurf": FK_BASIS}).json()
    frage = next(f for f in r["fragen"] if f.get("merkmal") == "SITZQUALI")
    assert "FK" not in frage["werte"]  # FK entschieden, BS/XX bleiben offen
    m = client.post("/api/material/90000001", json={"entwurf": None}).json()
    schluessel = {f["schluessel"] for f in d["fragen"]}
    assert m["fragen"] and {f["schluessel"] for f in m["fragen"]} <= schluessel  # Material zeigt Teilmenge
    assert all(f["positionen"] >= 1 for f in m["fragen"])


def test_entwurf_serverseitig_und_materialinfo(client):
    assert client.get("/api/entwurf?name=Erika").json() == {"entwurf": None}
    client.put("/api/entwurf", json={"name": "Erika", "entwurf": FK_BASIS})
    assert client.get("/api/entwurf?name=Erika").json()["entwurf"] == FK_BASIS
    client.put("/api/entwurf", json={"name": "Erika", "entwurf": {"regeln": [], "aliasse": []}})
    assert client.get("/api/entwurf?name=Erika").json() == {"entwurf": None}
    assert client.get("/api/materialinfo/0010000002").json() == {
        "matnr": "10000002",
        "kurztext": "Sitzkissen HR",
        "bekannt": True,
    }
    assert client.get("/api/materialinfo/77777777").json()["bekannt"] is False
