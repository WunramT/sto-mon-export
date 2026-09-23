"""Regression gegen bestätigte Reviews (D23). Prototyp: meldet nur, blockiert nichts.

Für jedes Root in `bestaetigt`: Soll = letzter Review-Import (Zeilen mit Status basis/unbedingt und Urteil
`richtig`), Ist = Positionen des Laufs mit Status basis/unbedingt. Vergleich über (Material, Parent, Menge) als
Multimenge; jede Abweichung ist rot und setzt den Lauf-Status `regression_fehlgeschlagen`.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from .explode import EXPORT_STATUS
from .lauf import beende_lauf, lade_aufloesung, lauf_status

NACHKOMMA = 6


def _schluessel(matnr, parent, menge) -> tuple:
    m = None if menge is None or pd.isna(menge) else round(float(menge), NACHKOMMA)
    return (str(matnr), str(parent), m)


def soll(eng: Engine) -> dict[str, Counter]:
    sql = """
        SELECT r.root_matnr, r.matnr, r.parent_matnr, r.menge, r.status, r.urteil
        FROM basis_bom.review r
        JOIN basis_bom.bestaetigt b USING (root_matnr)
        WHERE r.importiert = (SELECT max(importiert) FROM basis_bom.review x WHERE x.root_matnr = r.root_matnr)
    """
    out: dict[str, Counter] = {}
    with eng.connect() as con:
        for r in con.execute(sa.text(sql)).mappings():
            c = out.setdefault(r["root_matnr"], Counter())
            if r["status"] in EXPORT_STATUS and r["urteil"] == "richtig":
                c[_schluessel(r["matnr"], r["parent_matnr"], r["menge"])] += 1
    return out


def regress(eng: Engine, lauf_id: int) -> pd.DataFrame:
    """Abweichungen pro bestätigtem Root; setzt den Lauf-Status. Leeres Ergebnis = grün."""
    ziel = soll(eng)
    ist_df = lade_aufloesung(eng, lauf_id, list(ziel)) if ziel else None
    zeilen = []
    geprueft = []
    for root, s in sorted(ziel.items()):
        teil = ist_df[(ist_df["root_matnr"] == root) & ist_df["status"].isin(EXPORT_STATUS)]
        if ist_df[ist_df["root_matnr"] == root].empty:
            zeilen.append({"root_matnr": root, "art": "nicht_im_lauf", "matnr": None, "parent_matnr": None,
                           "menge": None, "anzahl": None})  # fmt: skip
            continue
        geprueft.append(root)
        ist = Counter(_schluessel(z.matnr, z.parent_matnr, z.menge_kum) for z in teil.itertuples())
        for art, diff in (("fehlt_im_lauf", s - ist), ("zusaetzlich_im_lauf", ist - s)):
            for (matnr, parent, menge), n in sorted(diff.items(), key=str):
                zeilen.append({"root_matnr": root, "art": art, "matnr": matnr, "parent_matnr": parent,
                               "menge": menge, "anzahl": n})  # fmt: skip
    df = pd.DataFrame(zeilen, columns=["root_matnr", "art", "matnr", "parent_matnr", "menge", "anzahl"])
    rot = df[df["art"] != "nicht_im_lauf"]
    status = "regression_fehlgeschlagen" if not rot.empty else ("regression_ok" if geprueft else None)
    if status and lauf_status(eng, lauf_id) not in ("fehler",):
        beende_lauf(eng, lauf_id, status, {"regression": {"geprueft": geprueft, "abweichungen": len(rot),
                                                          "nicht_im_lauf": int((df["art"] == "nicht_im_lauf").sum())}})  # fmt: skip
    return df
