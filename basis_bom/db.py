"""Datenbankzugriff und Ausführung der SQL-Dateien aus sql/."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import config

log = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _engine(url: str) -> Engine:
    return sa.create_engine(url, future=True)


def engine(url: str | None = None) -> Engine:
    return _engine(url or config.database_url())


def sql_files(subdir: str) -> list[Path]:
    return sorted((config.SQL_DIR / subdir).glob("*.sql"))


def run_sql_file(eng: Engine, path: Path) -> None:
    """Führt eine SQL-Datei als ein Skript aus (mehrere Statements erlaubt)."""
    sql = path.read_text(encoding="utf-8")
    raw = eng.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
    finally:
        raw.close()


def init_schema(eng: Engine) -> None:
    """Schemas anlegen und alle DDL-/Seed-Dateien in Reihenfolge ausführen (idempotent)."""
    with eng.begin() as con:
        con.execute(sa.text("CREATE SCHEMA IF NOT EXISTS sap_raw"))
        con.execute(sa.text("CREATE SCHEMA IF NOT EXISTS basis_bom"))
    for path in sql_files("schema"):
        log.info("schema: %s", path.name)
        run_sql_file(eng, path)


def init_views(eng: Engine) -> None:
    for path in sql_files("views"):
        log.info("view: %s", path.name)
        run_sql_file(eng, path)


def table_exists(eng: Engine, schema: str, table: str) -> bool:
    with eng.connect() as con:
        return con.execute(sa.text("SELECT to_regclass(:n)"), {"n": f"{schema}.{table}"}).scalar() is not None


def kanonische_merkmale(eng: Engine) -> list[str]:
    """Kanonische Merkmalnamen aus der Alias-Tabelle (D6), sonst die Liste aus EXPORT-PLAN Phase 3."""
    from .loader import MERKMALLISTE_DEFAULT

    if not table_exists(eng, "basis_bom", "alias"):
        return list(MERKMALLISTE_DEFAULT)
    with eng.connect() as con:
        rows = con.execute(
            sa.text(
                "SELECT DISTINCT merkmal FROM basis_bom.alias WHERE merkmal IS NOT NULL AND gueltig_bis IS NULL"
            )
        ).scalars()
        return sorted(set(rows) | set(MERKMALLISTE_DEFAULT))
