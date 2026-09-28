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


@pytest.fixture()
def regeln_sichern(fixture_db, app):
    """Regeln nach dem Test exakt wiederherstellen (auch „keine Regel“ statt OFFEN) – fixture_db ist sitzungsweit."""
    import sqlalchemy as sa

    with fixture_db.begin() as con:
        max_id = con.execute(sa.text("SELECT coalesce(max(id), 0) FROM basis_bom.regel")).scalar()
        t0 = con.execute(sa.text("SELECT clock_timestamp()")).scalar()
    yield
    with fixture_db.begin() as con:
        con.execute(sa.text("DELETE FROM basis_bom.regel WHERE id > :i"), {"i": max_id})
        con.execute(sa.text("UPDATE basis_bom.regel SET gueltig_bis = NULL WHERE gueltig_bis >= :t"), {"t": t0})
        con.execute(sa.text("DELETE FROM basis_bom.bestaetigt"))
    app.state.datenstand.dienst.cache_leeren()


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
    r = client.post("/api/uebernehmen", json={"entwurf": FK_BASIS, "von": "Test", "begruendung": "Test Übernahme"})
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
    d = client.post("/api/uebernehmen", json={"entwurf": doppelt, "von": "T", "begruendung": "Rang eins bitte"})
    assert d.status_code == 409 and d.json()["konflikte"][0]["art"] == "rang"
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


def test_review_bestaetigen_und_regression(client, fixture_db, regeln_sichern):
    d = client.post("/api/material/90000006", json={"entwurf": None}).json()
    alle = {p["id"]: {"urteil": "richtig"} for p in d["positionen"]}
    teil = dict(list(alle.items())[:1])
    r = client.post("/api/review/90000006", json={"von": "Erika", "urteile": teil})
    assert r.status_code == 200
    assert client.post("/api/bestaetigen/90000006", json={"von": "Erika"}).status_code == 400  # unvollständig
    assert client.post("/api/review/90000006", json={"von": "Erika", "urteile": alle}).status_code == 200
    # offene Position (technische Regel unentschieden) → nicht bestätigbar, auch wenn alles „richtig“ ist
    offen = client.post("/api/bestaetigen/90000006", json={"von": "Erika"})
    assert offen.status_code == 400 and "2 als falsch markiert" in offen.json()["fehler"]  # offen ≠ „richtig“
    rules.setze_regel(fixture_db, "PP4000_KS_VERERBEN", "vorhanden", "BASIS", 1, geaendert_von="test")
    rules.setze_regel(fixture_db, "SITZQUALI", "FK", "BASIS", 2, geaendert_von="test")
    client.app.state.datenstand.dienst.cache_leeren()
    d = client.post("/api/material/90000006", json={"entwurf": None}).json()
    assert {p["status"] for p in d["positionen"]}.isdisjoint({"manuell_prüfen", "unterhalb_manuell"}), d["positionen"]
    alle = {p["id"]: {"urteil": "richtig"} for p in d["positionen"]}
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
    fk_nie = {"regeln": [{"merkmal": "SITZQUALI", "wert": "FK", "status": "NICHT_BASIS", "rang": None,
                          "vorher": {"status": "BASIS", "rang": 2}}]}  # fmt: skip
    r = client.post("/api/uebernehmen", json={"entwurf": fk_nie, "von": "Test", "begruendung": "Test Regression"})
    assert r.status_code == 200
    try:
        d3 = client.post("/api/material/90000006", json={"entwurf": None}).json()
        assert d3["review"]["veraltet"] == 1
        from basis_bom import lauf

        lid2, _ = lauf.fuehre_aufloesung_aus(fixture_db, ["90000006"])
        assert not regress.regress(fixture_db, lid2).empty
    finally:
        pass


def test_manuelle_entscheidung_bestaetigen_und_export(client, regeln_sichern):
    """D25: offene Positionen per „fehlt“/„gehoert_nicht_rein“ entscheiden → bestätigbar, Export folgt."""
    d = client.post("/api/material/90000006", json={"entwurf": None}).json()
    urteile = {p["id"]: {"urteil": "fehlt" if p["matnr"] == "10000102" else
                         "gehoert_nicht_rein" if p["status"] == "manuell_prüfen" else "richtig"} for p in d["positionen"]}
    r = client.post("/api/review/90000006", json={"von": "Erika", "urteile": urteile,
                    "ergaenzt": [{"parent_pfad": "90000006", "matnr": "10000999", "menge": 3, "meins": "ST"}]})  # fmt: skip
    assert r.status_code == 200, r.text
    assert client.post("/api/bestaetigen/90000006", json={"von": " "}).status_code == 400
    assert client.post("/api/bestaetigen/90000006", json={"von": "Erika"}).status_code == 200
    csv = client.get("/api/export/90000006").text
    assert ";10000102;" in csv and ";10000016;" not in csv and ";10000999;" in csv


def test_neues_kuerzel_uebernehmen(client, regeln_sichern, fixture_db):
    """Kürzel ohne Zuordnung kommen als OFFEN in die Oberfläche; Übernehmen darf daran keinen Konflikt sehen."""
    k = next(x for x in client.post("/api/regeln", json={"entwurf": None}).json()["kuerzel"] if x["alias"] == "ZZ")
    e = {"aliasse": [{"alias": "ZZ", "merkmal": "SITZTIEFE", "status": "BASIS",
                      "vorher": {"merkmal": k["merkmal"], "status": k["status"]}}]}  # fmt: skip
    r = client.post("/api/uebernehmen", json={"entwurf": e, "von": "T", "begruendung": "ZZ ist Sitztiefe"})
    assert r.status_code == 200, r.text
    assert rules.lade_regelstand(fixture_db).aliasse["ZZ"].merkmal == "SITZTIEFE"
    import sqlalchemy as sa

    with fixture_db.begin() as con:  # Alias wieder entfernen (regeln_sichern setzt nur Regeln zurück)
        con.execute(sa.text("DELETE FROM basis_bom.alias WHERE alias = 'ZZ'"))


def test_widerspruch_und_export_unter_ausgeschlossener_baugruppe(client, regeln_sichern):
    d = client.post("/api/material/90000001", json={"entwurf": None}).json()
    pos = {p["matnr"]: p for p in d["positionen"] if p["matnr"]}
    urteile = {p["id"]: {"urteil": "richtig"} for p in d["positionen"] if p["status"] not in ("manuell_prüfen", "unterhalb_manuell")}
    for p in d["positionen"]:
        if p["status"] in ("manuell_prüfen", "unterhalb_manuell"):
            urteile[p["id"]] = {"urteil": "fehlt"}
    urteile[pos["10000006"]["id"]] = {"urteil": "gehoert_nicht_rein"}  # Baugruppe raus, Kinder 10000201/202 „rein“
    assert client.post("/api/review/90000001", json={"von": "E", "urteile": urteile}).status_code == 200
    b = client.post("/api/bestaetigen/90000001", json={"von": "E"})
    assert b.status_code == 400 and "ausgeschlossenen Baugruppe" in b.json()["fehler"]
    csv = client.get("/api/export/90000001").text
    assert ";10000201;" not in csv and ";10000202;" not in csv and ";10000102;" in csv


def test_bestaetigt_veraltet_und_auswirkung(client, regeln_sichern):
    d = client.post("/api/material/90000005", json={"entwurf": None}).json()
    urteile = {p["id"]: {"urteil": "fehlt" if p["status"] == "manuell_prüfen" else "richtig"} for p in d["positionen"]}
    assert client.post("/api/review/90000005", json={"von": "E", "urteile": urteile}).status_code == 200
    assert client.post("/api/bestaetigen/90000005", json={"von": "E"}).status_code == 200
    zustand = {m["matnr"]: m["zustand"] for m in client.get("/api/materialien").json()}
    assert zustand["90000005"] == "bestaetigt"
    a = client.post("/api/auswirkung", json={"entwurf": FK_BASIS}).json()
    m5 = next(m for m in a["materialien"] if m["matnr"] == "90000005")
    assert m5["bestaetigt"] is True and m5["bestaetigt_betroffen"] is False
    r = client.post("/api/uebernehmen", json={"entwurf": FK_BASIS, "von": "T", "begruendung": "FK wird Basis"})
    assert r.status_code == 200
    # FK=Basis macht 10000102 regelbasiert zu „Basis“ – das war manuell schon „rein“: Export unverändert → aktuell
    zustand = {m["matnr"]: m["zustand"] for m in client.get("/api/materialien").json()}
    assert zustand["90000005"] == "bestaetigt"
    # Regel, die den Export ändert (HR nie Basis) → veraltet
    hr = {"regeln": [{"merkmal": "SITZQUALI", "wert": "HR", "status": "NICHT_BASIS", "rang": None,
                      "vorher": {"status": "BASIS", "rang": 1}},
                     {"merkmal": "SITZQUALI", "wert": "FK", "status": "BASIS", "rang": 1,
                      "vorher": {"status": "BASIS", "rang": 2}}]}  # fmt: skip
    a2 = client.post("/api/auswirkung", json={"entwurf": hr}).json()
    assert any(m["matnr"] == "90000005" and m["bestaetigt_betroffen"] for m in a2["materialien"])
    assert client.post("/api/uebernehmen", json={"entwurf": hr, "von": "T", "begruendung": "HR nicht mehr"}).status_code == 200
    zustand = {m["matnr"]: m["zustand"] for m in client.get("/api/materialien").json()}
    assert zustand["90000005"] == "bestaetigt_veraltet"
    assert client.post("/api/material/90000005", json={"entwurf": None}).json()["review"]["bestaetigt"]["veraltet"] is True


def test_ergaenzt_unter_ausgeschlossener_baugruppe_und_klassenposition(client, regeln_sichern):
    d = client.post("/api/material/90000001", json={"entwurf": None}).json()
    pos = {p["matnr"] or f"K{p['posnr']}": p for p in d["positionen"]}
    raus = pos["10000003"]  # nicht in der Basis
    urteile = {p["id"]: {"urteil": "fehlt" if p["status"] in ("manuell_prüfen", "unterhalb_manuell") else "richtig"}
               for p in d["positionen"]}  # fmt: skip
    r = client.post("/api/review/90000001", json={"von": "E", "urteile": urteile, "ergaenzt": [
        {"parent_pfad": raus["id"], "matnr": "10000013", "menge": 1}]})  # fmt: skip
    assert r.status_code == 200
    b = client.post("/api/bestaetigen/90000001", json={"von": "E"}).json()["fehler"]
    import re

    assert "ausgeschlossenen Baugruppe" in b and re.search(r"[1-9]\d* als falsch markiert", b)  # Klassenpos. ohne Material
    assert ";10000013;" not in client.get("/api/export/90000001").text


def test_kein_root_material(client):
    r = client.post("/api/material/10000001", json={"entwurf": None})
    assert r.status_code == 400 and "kein Root-Material" in r.json()["fehler"]
    u = client.post("/api/material/99999999", json={"entwurf": None})
    assert u.status_code == 400 and "gibt es im SAP-Export nicht" in u.json()["fehler"]


def test_uebernehmen_braucht_begruendung(client):
    r = client.post("/api/uebernehmen", json={"entwurf": FK_BASIS, "von": "Test", "begruendung": " kurz"})
    assert r.status_code == 400 and "begründen" in r.json()["fehler"]


def test_review_konflikt(client):
    d = client.post("/api/material/90000005", json={"entwurf": None}).json()
    stand = d["review"]["stand"]
    eine = {d["positionen"][0]["id"]: {"urteil": "richtig"}}
    assert client.post("/api/review/90000005", json={"von": "A", "urteile": eine, "stand": stand}).status_code == 200
    # B hat noch den alten Stand geladen → Konflikt statt Überschreiben
    k = client.post("/api/review/90000005", json={"von": "B", "urteile": {}, "stand": stand})
    assert k.status_code == 409 and "A hat dieses Material" in k.json()["fehler"]
    neu = client.post("/api/material/90000005", json={"entwurf": None}).json()["review"]["stand"]
    assert client.post("/api/review/90000005", json={"von": "B", "urteile": eine, "stand": neu}).status_code == 200


def test_fehlerformat_und_nicht_bereit(app, client):
    assert client.get("/api/gibtsnicht").json() == {"fehler": "Nicht gefunden"}
    ds = app.state.datenstand
    alt = ds.status.zustand
    ds.status.zustand = "fehler"
    try:
        r = client.get("/api/meta")
        assert r.status_code == 503 and "fehlgeschlagen" in r.json()["fehler"]
    finally:
        ds.status.zustand = alt


def test_neu_laden_skript(monkeypatch):
    """scripts/neu_laden.py (Jenkins RELOAD_EXPORTS): Methode, Body und Token kommen beim Backend an."""
    import importlib.util
    import io
    import json

    spec = importlib.util.spec_from_file_location("neu_laden", Path(__file__).parent.parent / "backend/scripts/neu_laden.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    gesehen = []

    def urlopen(req, timeout):
        gesehen.append((req.get_method(), req.full_url, req.data, req.headers.get("Authorization")))
        antwort = {"access_token": "T"} if req.full_url.endswith("/auth/login") else {
            "dateien": [], "exports_dir": "/x", "zustand": "bereit"}
        return io.BytesIO(json.dumps(antwort).encode())

    monkeypatch.setattr(modul.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("MASTER_PASSWORD_ADMIN", "pw")
    monkeypatch.setattr(modul.sys, "argv", ["neu_laden.py"])
    modul.main()
    assert gesehen[0][0] == "POST" and json.loads(gesehen[0][2]) == {"passwort": "pw"}
    assert gesehen[1][:2] == ("GET", modul.BASIS + "/datenstand")
    assert gesehen[2][:2] == ("POST", modul.BASIS + "/datenstand/neu-laden") and gesehen[2][3] == "Bearer T"


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
