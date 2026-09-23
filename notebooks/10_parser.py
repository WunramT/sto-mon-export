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
# # 10 – Parser
#
# Alle distinct `KNNAM` der geladenen CUKB parsen und die Verteilung zeigen: parsbar / unbekannter Alias /
# offener Alias (z. B. `OPTIK` ohne Suffix) / Systemregel-Kandidat / nicht parsbar (D6, D7, D11).

# %%
import pandas as pd

from basis_bom import db, rules
from basis_bom.parser import Parser
from basis_bom.source import SapSource

eng = db.engine()
rs = rules.lade_regelstand(eng)
parser = Parser(rs.alias_liste())
src = SapSource.from_db(eng)
namen = sorted(set(src.roh("CUKB")["KNNAM"]))
print(f"{len(namen)} distinct KNNAM, {len(rs.aliasse)} Aliasse")

# %%
ergebnisse = [parser.parse(n) for n in namen]
df = pd.DataFrame(
    {
        "KNNAM": [e.roh for e in ergebnisse],
        "klasse": [e.klasse for e in ergebnisse],
        "paare": [e.paare for e in ergebnisse],
        "unbekannt": [e.unbekannte_aliasse for e in ergebnisse],
        "offen": [e.offene_aliasse for e in ergebnisse],
        "fehler": [e.fehler for e in ergebnisse],
    }
)
df["klasse"].value_counts().rename_axis("klasse").reset_index(name="anzahl")

# %% [markdown]
# ## Nicht parsbar (D11) – Liste für den Menschen

# %%
df[df["klasse"] == "nicht_parsbar"][["KNNAM", "fehler"]]

# %% [markdown]
# ## Unbekannte Kürzel (D6) nach Häufigkeit

# %%
df.explode("unbekannt").dropna(subset=["unbekannt"])["unbekannt"].value_counts().head(50)

# %% [markdown]
# ## Systemregel-Kandidaten (D7)

# %%
df[df["klasse"] == "systemregel_kandidat"][["KNNAM"]]

# %% [markdown]
# ## Beobachtete Werte pro Merkmal (Grundlage der Rangliste, Ersatz `cawn_fehlt`)

# %%
paare = df.explode("paare").dropna(subset=["paare"])
paare = pd.DataFrame(paare["paare"].tolist(), columns=["merkmal", "wert"])
paare["status"] = [
    rs.status(m, w) or "(neu → OFFEN)" for m, w in zip(paare["merkmal"], paare["wert"], strict=True)
]
paare.value_counts().rename("anzahl").reset_index().sort_values(
    ["merkmal", "anzahl"], ascending=[True, False]
)
