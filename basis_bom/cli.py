"""Kommandozeile `basis-bom`."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from . import config, db

app = typer.Typer(help="Basis-Stückliste (Prototyp)", no_args_is_help=True)
db_app = typer.Typer(help="Datenbank anlegen und laden", no_args_is_help=True)
app.add_typer(db_app, name="db")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )


@db_app.command("init")
def db_init(
    fixtures: bool = typer.Option(False, "--fixtures", help="tests/fixtures/*.csv nach sap_raw laden"),
    from_dir: Path | None = typer.Option(None, "--from-dir", help="maßgebliche Exporte (docs/EXPORTE.md)"),
) -> None:
    """Schemas anlegen (idempotent) und optional SAP-Daten nach `sap_raw` laden."""
    from . import loader, pruefpunkte

    eng = db.engine()
    db.init_schema(eng)
    if fixtures and from_dir:
        raise typer.BadParameter("--fixtures und --from-dir schließen sich aus")
    if fixtures:
        erg = loader.lade_fixtures()
        loader.schreibe(eng, erg, quelle_roots="fixtures")
        typer.echo(f"Fixtures geladen: {', '.join(f'{t}={len(d)}' for t, d in erg.tabellen.items())}")
    elif from_dir:
        erg = loader.lade_verzeichnis(from_dir, db.kanonische_merkmale(eng))
        loader.schreibe(eng, erg, quelle_roots=loader.ROOT_XLSX)
        pruefpunkte.schreibe_fragen(pruefpunkte.berichte(erg, set(db.kanonische_merkmale(eng))))
        typer.echo(f"Exporte geladen aus {from_dir}; Prüfpunkte in {config.FRAGEN_MD}")
    db.init_views(eng)
    typer.echo("db init: ok")


if __name__ == "__main__":
    app()
