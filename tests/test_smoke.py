import sqlalchemy as sa

import basis_bom
from basis_bom.cli import app


def test_paket_importierbar():
    assert basis_bom.__version__
    assert app is not None


def test_select_1(pg_engine):
    with pg_engine.connect() as con:
        assert con.execute(sa.text("SELECT 1")).scalar() == 1
