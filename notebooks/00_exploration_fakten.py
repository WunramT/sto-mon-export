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
# # 00 – Exploration: offene Fakten F1–F6
#
# Verbindung zur Dev-Datenbank prüfen und die offenen Fakten aus `docs/DECISIONS.md` als Zahlen ausgeben.

# %%
import sqlalchemy as sa

from basis_bom import db

eng = db.engine()
with eng.connect() as con:
    print("SELECT 1 →", con.execute(sa.text("SELECT 1")).scalar())

# %% [markdown]
# ## Geladene Tabellen und Stichtag

# %%
import pandas as pd

from basis_bom import fakten
from basis_bom.source import SapSource

src = SapSource.from_db(eng)
print("Stichtag:", src.stichtag, "| Marker:", sorted(src.marker))
for w in src.warnungen:
    print("WARNUNG:", w)
pd.DataFrame(
    [(t, len(src.roh(t)), src.export_daten.get(t)) for t in sorted(src.export_daten)],
    columns=["tabelle", "zeilen", "export_datum"],
)

# %% [markdown]
# ## F1–F6 als Zahlen

# %%
fakten.uebersicht(src)

# %% [markdown]
# ### F1 – Mehrfachzeilen in CUKB pro KNNUM

# %%
fakten.f1_cukb_mehrfach(src).head(30)

# %% [markdown]
# ### F2 – Negationen in Bedingungsnamen

# %%
fakten.f2_negationen(src)

# %% [markdown]
# ### F3 – Alternativpositionen (ALPGR/ALPRF)

# %%
fakten.f3_alternativpositionen(src)

# %% [markdown]
# ### F4 – KNART-Verteilung an STPO-Positionen

# %%
fakten.f4_knart_verteilung(src)

# %% [markdown]
# Wo gehen Beziehungen verloren (CUOB → CUKB → KNSTA → D14)? Und welche KNSTA/KNART-Werte gibt es roh?

# %%
fakten.f4_trichter(src)

# %%
fakten.cukb_werte(src)

# %% [markdown]
# ### F5 – Materialien mit mehr als einem STLNR (D15)

# %%
fakten.f5_mehrere_stlnr(src)

# %% [markdown]
# ### F6 – BMENG ≠ 1

# %%
fakten.f6_bmeng(src)
