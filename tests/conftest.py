"""Gemeinsame Test-Fixtures.

DB-Tests laufen nur gegen die lokale Dev-Datenbank: `BASIS_BOM_TEST_DATABASE_URL`, sonst `DATABASE_URL`
(im Devcontainer der `db`-Service). Ohne erreichbare Datenbank werden sie übersprungen, nie gegen Prod.
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa


def _test_url() -> str | None:
    url = os.environ.get("BASIS_BOM_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        return None
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@pytest.fixture(scope="session")
def pg_engine():
    url = _test_url()
    if url is None:
        pytest.skip("keine Test-Datenbank konfiguriert (DATABASE_URL)")
    eng = sa.create_engine(url, future=True)
    try:
        with eng.connect() as con:
            con.execute(sa.text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - Umgebung
        pytest.skip(f"Test-Datenbank nicht erreichbar: {exc}")
    return eng
