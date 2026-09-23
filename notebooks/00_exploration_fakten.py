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
