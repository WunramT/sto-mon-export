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
# # 30 – Auflösung Ebene für Ebene
#
# Ein Material auflösen (ohne zu speichern) und jede Ebene mit Rangentscheidung und Spur zeigen (D9–D18).

# %%
import pandas as pd

from basis_bom import anzeige, db, lauf, rules
from basis_bom.explode import Aufloeser
from basis_bom.source import SapSource

pd.set_option("display.max_colwidth", 120)
eng = db.engine()
src = SapSource.from_db(eng)
regeln = rules.lade_regelstand(eng)
aufl = Aufloeser(src, regeln)
roots, ausschluss = lauf.roots_aus_db(eng)
geeignet = [r for r in roots if r not in ausschluss and aufl.root_pruefung(r) is None]
print(
    f"Stichtag {src.stichtag}, Marker {sorted(src.marker)}; {len(geeignet)}/{len(roots)} Root-Materialien auflösbar"
)

# %%
MATNR = geeignet[0] if geeignet else None  # hier eine Materialnummer eintragen
erg = aufl.loese_alle([MATNR])
df = erg.df()
print(MATNR, "→", len(df), "Positionen;", erg.statistik()["status"])

# %% [markdown]
# ## Rangentscheidung pro Stückliste

# %%
pd.DataFrame(
    [
        {"stlnr": s, "stlal": a, "bmeng": e.bmeng, "gewaehlt": e.wahl.gewaehlt, "marker": e.wahl.marker}
        for (s, a), e in aufl._ebenen.items()
    ]
)

# %% [markdown]
# ## Ebene für Ebene mit Spur

# %%
df["spur_lesbar"] = df["spur"].map(anzeige.spur_lesbar)
spalten = [
    "ebene",
    "stlnr",
    "posnr",
    "parent_matnr",
    "matnr",
    "menge",
    "menge_kum",
    "status",
    "grund",
    "spur_lesbar",
]
for ebene, teil in df.groupby("ebene"):
    print(f"\n=== Ebene {ebene} ({len(teil)} Positionen) ===")
    print(teil[spalten].to_string())

# %% [markdown]
# ## Baum

# %%
print(anzeige.baum_text(df, kurztext=src.lookup("MAKT", "MAKTX")))
