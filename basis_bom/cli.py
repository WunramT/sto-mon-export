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
    alle_stuecklisten: bool = typer.Option(
        False,
        "--alle-stuecklisten",
        help="S nicht auf die von den Roots erreichbaren Stücklisten beschränken",
    ),
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
        try:
            erg = loader.lade_verzeichnis(
                from_dir, db.kanonische_merkmale(eng), nur_erreichbar=not alle_stuecklisten
            )
        except loader.HeaderFehler as exc:
            if exc.erg is not None:
                typer.echo(f"Header-Bericht: {_header_bericht(exc.erg.protokoll.values())}", err=True)
            raise typer.Exit(f"FEHLER: {exc}") from None
        typer.echo(f"Header-Bericht: {_header_bericht(erg.protokoll.values())}")
        loader.schreibe(eng, erg, quelle_roots=loader.ROOT_XLSX)
        pruefpunkte.schreibe_fragen(pruefpunkte.berichte(erg, set(db.kanonische_merkmale(eng))))
        typer.echo(f"Exporte geladen aus {from_dir}; Prüfpunkte in {config.FRAGEN_MD}")
    db.init_views(eng)
    typer.echo("db init: ok")


def _header_bericht(protokolle) -> Path:
    from . import loader

    ziel = config.out_dir() / "header_bericht.md"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(loader.header_bericht(protokolle), encoding="utf-8")
    return ziel


@db_app.command("headers")
def db_headers(from_dir: Path = typer.Option(..., "--from-dir", exists=True, file_okay=False)) -> None:
    """Nur Kopfzeilen der maßgeblichen Exporte lesen und die Zuordnung zeigen (schnell)."""
    from . import headers, loader

    prot = loader.lese_header(from_dir)
    for p in prot:
        fehlend = [c for c in headers.SPALTEN.get(p.tabelle, []) if c not in p.header.values()]
        unbekannt = [h for h, t in p.header.items() if t is None]
        typer.echo(f"{p.tabelle} ({p.datei}): nicht zugeordnet {fehlend or '–'}")
        if fehlend:
            typer.echo(f"    unbekannte Header: {unbekannt}")
    typer.echo(f"Header-Bericht: {_header_bericht(prot)}")


@app.command()
def sql(
    abfrage: str = typer.Argument(..., help='SQL, z. B. "SELECT * FROM basis_bom.offene_faelle_ursache"'),
    csv_datei: Path | None = typer.Option(None, "--csv", help="Ergebnis zusätzlich als CSV speichern"),
    max_zeilen: int = typer.Option(200, "--max", help="höchstens so viele Zeilen anzeigen"),
) -> None:
    """SQL gegen die Dev-Datenbank ausführen und als Tabelle ausgeben (ohne psql)."""
    import pandas as pd
    import sqlalchemy as sa

    with db.engine().connect() as con:
        df = pd.read_sql(sa.text(abfrage), con)
    with pd.option_context("display.max_rows", max_zeilen, "display.max_columns", None, "display.width", 250,
                           "display.max_colwidth", 80):  # fmt: skip
        typer.echo(df.head(max_zeilen).to_string(index=False))
    typer.echo(f"({len(df)} Zeilen)")
    if csv_datei:
        df.to_csv(csv_datei, index=False, sep=";")
        typer.echo(f"CSV: {csv_datei}")


@app.command()
def run(
    matnr: list[str] | None = typer.Option(None, "--matnr", help="nur diese Root-Materialien (mehrfach)"),
    out: Path | None = typer.Option(None, "--out", help="Ausgabeordner (Default: out/)"),
    ohne_review: bool = typer.Option(False, "--ohne-review", help="keine Review-Blätter schreiben"),
) -> None:
    """Prototyp-Lauf (D23): check → Auflösung → regress (nur Meldung) → export + Review-Blätter."""
    from . import pipeline

    b = pipeline.run(db.engine(), matnr, out, review_blaetter=not ohne_review)
    rot = b.pruefungen[b.pruefungen["ok"] == False]  # noqa: E712
    typer.echo(f"Lauf {b.lauf_id}: Prüfungen {len(b.pruefungen)} ({len(rot)} rot)")
    for r in rot.itertuples():
        typer.echo(f"  ROT {r.pruefung}: {r.detail}")
    st = b.statistik
    typer.echo(
        f"Auflösung: {st['roots_aufgeloest']} Root-Materialien, {st['positionen']} Positionen {st['status']}"
    )
    for u in st["roots_uebersprungen"]:
        typer.echo(f"  übersprungen {u['matnr']}: {u['grund']}")
    typer.echo(f"Marker: {', '.join(st['marker']) or '–'}; Ebenen-Marker: {st['ebene_marker']}")
    for w in st["warnungen"]:
        typer.echo(f"  WARNUNG {w}")
    rot_reg = b.regression[b.regression["art"] != "nicht_im_lauf"] if not b.regression.empty else b.regression
    typer.echo(
        f"Regression: {'ROT, ' + str(len(rot_reg)) + ' Abweichungen' if len(rot_reg) else 'grün/keine'}"
    )
    typer.echo(f"Dateien ({len(b.dateien)}): {b.dateien[0].parent if b.dateien else '–'}")
    typer.echo("Zeiten: " + ", ".join(f"{k} {v:.1f}s" for k, v in b.sekunden.items()))


def _lauf(lauf_id: int | None) -> int:
    from . import lauf

    lid = lauf_id or lauf.letzter_lauf_id(db.engine())
    if lid is None:
        raise typer.BadParameter("kein abgeschlossener Lauf vorhanden – zuerst `basis-bom run`")
    return lid


def _ausgabe(lauf_id: int, out: Path | None) -> Path:
    return (out or config.out_dir()) / f"lauf_{lauf_id}"


@app.command()
def check() -> None:
    """Konsistenz- und Exportprüfungen (sql/checks); Prototyp: nur Meldung."""
    from . import checks

    df = checks.pruefe(db.engine())
    for r in df.itertuples():
        zeichen = {True: "OK  ", False: "ROT ", None: "--  "}[r.ok if r.ok in (True, False) else None]
        typer.echo(f"{zeichen}{r.pruefung}: {r.detail}")
    rot = int((df["ok"] == False).sum())  # noqa: E712
    typer.echo(f"{len(df)} Prüfungen, {rot} rot")


@app.command()
def export(
    lauf_id: int | None = typer.Option(None, "--lauf", help="Default: letzter Lauf"),
    matnr: list[str] | None = typer.Option(None, "--matnr"),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """SAP-Format-Export (D19) pro Root-Material und gesamt."""
    from . import export as exp
    from . import lauf
    from .source import SapSource

    eng = db.engine()
    lid = _lauf(lauf_id)
    df = lauf.lade_aufloesung(eng, lid, matnr)
    for p in exp.exportiere(df, SapSource.from_db(eng), _ausgabe(lid, out)):
        typer.echo(f"Export: {p}")


@app.command("review-export")
def review_export(
    matnr: list[str] = typer.Argument(..., help="Root-Materialien"),
    lauf_id: int | None = typer.Option(None, "--lauf", help="Default: letzter Lauf"),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Review-Blatt (XLSX) pro Root-Material für den Fachbereich (D24)."""
    from . import lauf, review
    from .source import SapSource

    eng = db.engine()
    lid = _lauf(lauf_id)
    df = lauf.lade_aufloesung(eng, lid, matnr)
    src, stat = SapSource.from_db(eng), lauf.lade_statistik(eng, lid)
    for m in matnr:
        m = m.strip().lstrip("0")
        if df[df["root_matnr"] == m].empty:
            typer.echo(f"{m}: nicht im Lauf {lid}", err=True)
            continue
        p = review.review_blatt(df, src, lid, m, stat, _ausgabe(lid, out) / m / f"review_{m}.xlsx")
        typer.echo(f"Review-Blatt: {p}")


@app.command("review-import")
def review_import(
    datei: list[Path] = typer.Argument(..., exists=True, dir_okay=False),
    reviewer: str = typer.Option(..., "--reviewer", help="Name des Prüfers"),
) -> None:
    """Ausgefüllte Review-Blätter nach `basis_bom.review` (vollständig richtig → `bestaetigt`)."""
    from . import review

    for d in datei:
        erg = review.importiere(db.engine(), d, reviewer)
        typer.echo(f"{d.name}: {erg['zeilen']} Urteile, {erg['ohne_urteil']} ohne Urteil, bestätigt: "
                   f"{', '.join(erg['bestaetigt']) or '–'}")  # fmt: skip


@app.command()
def regress(lauf_id: int | None = typer.Option(None, "--lauf", help="Default: letzter Lauf")) -> None:
    """Abgleich gegen bestätigte Reviews (D23). Prototyp: meldet nur."""
    from . import regress as reg

    lid = _lauf(lauf_id)
    df = reg.regress(db.engine(), lid)
    if df.empty:
        typer.echo(f"Regression Lauf {lid}: grün (oder nichts bestätigt)")
        return
    typer.echo(df.to_string(index=False))
    rot = df[df["art"] != "nicht_im_lauf"]
    typer.echo(f"Regression Lauf {lid}: {'ROT' if len(rot) else 'grün'} – {len(rot)} Abweichungen")


if __name__ == "__main__":
    app()
