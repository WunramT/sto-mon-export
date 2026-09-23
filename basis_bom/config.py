"""Laufzeitkonfiguration aus der Umgebung."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
LEGACY_SCRIPT = REPO_ROOT / "legacy" / "basis_bom_v0.py"
FRAGEN_MD = REPO_ROOT / "docs" / "FRAGEN.md"

WERKS = "4000"
STLAN = "1"


def database_url() -> str:
    """DATABASE_URL als SQLAlchemy-URL mit psycopg-3-Treiber."""
    url = os.environ.get("DATABASE_URL", "postgresql://basis:basis@localhost:5432/basis")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def exports_dir() -> Path:
    return Path(os.environ.get("EXPORTS_DIR", "/data/exports"))


def out_dir() -> Path:
    return Path(os.environ.get("BASIS_BOM_OUT", REPO_ROOT / "out"))


def prod_mode() -> bool:
    """Prod: abweichende export_datum sind ein Fehler statt einer Warnung (D14, docs/EXPORTE.md)."""
    return os.environ.get("BASIS_BOM_MODE", "dev").lower() == "prod"
