"""Phase 9: alle Notebooks laufen ohne Codeänderung gegen die Fixture-Datenbank; .ipynb liegt gepaart daneben."""

import runpy
from pathlib import Path

import pytest

NOTEBOOKS = sorted((Path(__file__).parent.parent / "notebooks").glob("[0-9]*.py"))


@pytest.mark.parametrize("nb", NOTEBOOKS, ids=[n.stem for n in NOTEBOOKS])
def test_notebook_laeuft(nb, fixture_db, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", fixture_db.url.render_as_string(hide_password=False))
    assert nb.with_suffix(".ipynb").exists(), "jupytext --sync vergessen?"
    runpy.run_path(str(nb), run_name="__main__")
    if nb.stem == "90_debug_material":
        out = capsys.readouterr().out
        assert "90000001 Sessel STO Basis" in out and "(+1 eingeklappt)" in out
