# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: basis-bom
#     language: python
#     name: basis-bom
# ---

# %% [markdown]
# # 20 – Ranking pro Ebene
#
# Für jede Stückliste (STLNR) unabhängig: pro Merkmal gewinnt der vorkommende BASIS-Wert mit bestem Rang (D2),
# `SITZHOEHE` numerisch (D3), ohne Rangwert Marker `kein_rang_fuer:<M>` (D4).

# %%
import pandas as pd

from basis_bom import db, rules
from basis_bom.parser import Parser
from basis_bom.ranking import waehle
from basis_bom.source import SapSource

eng = db.engine()
rs = rules.lade_regelstand(eng)
parser = Parser(rs.alias_liste())
src = SapSource.from_db(eng)

# %% [markdown]
# ## Rangliste (Regelstand)

# %%
pd.DataFrame([r.__dict__ for r in rs.regeln.values()]).sort_values(["merkmal", "status", "rang"])

# %% [markdown]
# ## Wahl pro Stückliste

# %%
zeilen = []
for stlnr, pos in src.positionen.items():
    paare = []
    for knobj in set(pos["KNOBJ"]) - {"", "0"}:
        for knnum in src.knnum_pro_knobj.get(knobj, []):
            bez = src.beziehungen.get(knnum)
            if bez:
                paare += parser.parse(bez["knnam"]).paare
    wahl = waehle(paare, rs)
    zeilen.append({"stlnr": stlnr, "gewaehlt": wahl.gewaehlt, "marker": wahl.marker})
pd.DataFrame(zeilen)
