"""Kommandozeile `basis-bom`."""

from __future__ import annotations

import logging

import typer

from . import db

app = typer.Typer(help="Basis-Stückliste (Prototyp)", no_args_is_help=True)
db_app = typer.Typer(help="Datenbank anlegen und laden", no_args_is_help=True)
app.add_typer(db_app, name="db")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )


@db_app.command("init")
def db_init() -> None:
    """Schemas `sap_raw` und `basis_bom` anlegen (idempotent)."""
    eng = db.engine()
    db.init_schema(eng)
    db.init_views(eng)
    typer.echo("db init: ok")


if __name__ == "__main__":
    app()
