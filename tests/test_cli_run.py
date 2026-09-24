"""Phase 8: `basis-bom run` erzeugt Export und Review-Blätter."""

from typer.testing import CliRunner

from basis_bom import pipeline
from basis_bom.cli import app


def test_pipeline_run(fixture_db, tmp_path):
    b = pipeline.run(fixture_db, ["90000001", "90000002", "90000003"], tmp_path)
    namen = {p.name for p in b.dateien}
    assert {"grundversion_sap_format.csv", "90000001_sap_format.csv", "review_90000001.xlsx"} <= namen
    assert {u["matnr"] for u in b.statistik["roots_uebersprungen"]} == {"90000002", "90000003"}
    assert b.sekunden["gesamt"] < 300


def test_cli_run(fixture_db, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fixture_db.url.render_as_string(hide_password=False))
    res = CliRunner().invoke(app, ["run", "--matnr", "90000001", "--out", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "Auflösung: 1 Root-Materialien" in res.output
    assert list(tmp_path.glob("lauf_*/90000001/review_90000001.xlsx"))
    res = CliRunner().invoke(app, ["check"])
    assert res.exit_code == 0 and "Prüfungen" in res.output


def test_cli_sql(fixture_db, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", fixture_db.url.render_as_string(hide_password=False))
    ziel = tmp_path / "x.csv"
    res = CliRunner().invoke(app, ["sql", "SELECT 1 AS eins", "--csv", str(ziel)])
    assert res.exit_code == 0 and "eins" in res.output and ziel.exists()
