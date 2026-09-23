"""Gemeinsame Test-Fixtures.

DB-Tests laufen nur lokal: gegen `BASIS_BOM_TEST_DATABASE_URL`, sonst gegen eine eigene Datenbank
`<name>_test` auf dem Server aus `DATABASE_URL` (im Devcontainer der `db`-Service). Die Test-Datenbank wird pro
Sitzung neu angelegt; Dev-Daten bleiben unberührt. Ohne erreichbare Datenbank werden DB-Tests übersprungen.
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url


def _url(url: str) -> str:
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@pytest.fixture(scope="session")
def pg_engine():
    if os.environ.get("BASIS_BOM_TEST_DATABASE_URL"):
        url = make_url(_url(os.environ["BASIS_BOM_TEST_DATABASE_URL"]))
    elif os.environ.get("DATABASE_URL"):
        basis = make_url(_url(os.environ["DATABASE_URL"]))
        url = basis.set(database=f"{basis.database}_test")
        try:
            admin = sa.create_engine(basis, isolation_level="AUTOCOMMIT")
            with admin.connect() as con:
                con.execute(sa.text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
                con.execute(sa.text(f'CREATE DATABASE "{url.database}"'))
            admin.dispose()
        except Exception as exc:  # pragma: no cover - Umgebung
            pytest.skip(f"Test-Datenbank nicht anlegbar: {exc}")
    else:
        pytest.skip("keine Test-Datenbank konfiguriert (DATABASE_URL)")
    eng = sa.create_engine(url, future=True)
    try:
        with eng.connect() as con:
            con.execute(sa.text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - Umgebung
        pytest.skip(f"Test-Datenbank nicht erreichbar: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def fixture_db(pg_engine):
    """Test-Datenbank mit Schema, Seeds und geladenen Fixtures."""
    from basis_bom import db, loader

    db.init_schema(pg_engine)
    loader.schreibe(pg_engine, loader.lade_fixtures(), quelle_roots="fixtures")
    db.init_views(pg_engine)
    return pg_engine
