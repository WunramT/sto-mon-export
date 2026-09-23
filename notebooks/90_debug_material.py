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
# # 90 – Debug: ein Material
#
# Materialnummer eintragen und alle Zellen ausführen. Zeigt den Baum mit Status (ausgeschlossene Zweige
# eingeklappt, aber sichtbar), pro Stückliste die Rangentscheidung und pro Position die Spur (D18). Damit werden
# Review-Urteile begründet (D24). Aufgelöst wird mit dem aktuellen Regelstand, nichts wird gespeichert.

# %%
MATNR = "90000001"  # ← Materialnummer (führende Nullen egal)

# %%
import json

import pandas as pd

from basis_bom import anzeige, db, lauf, rules
from basis_bom.explode import Aufloeser
from basis_bom.source import SapSource

pd.set_option("display.max_colwidth", 200)
pd.set_option("display.width", 250)
IM_NOTEBOOK = "get_ipython" in globals()
eng = db.engine()
src = SapSource.from_db(eng)
regeln = rules.lade_regelstand(eng)
aufl = Aufloeser(src, regeln)
matnr = MATNR.strip().lstrip("0")
kurztext = src.lookup("MAKT", "MAKTX")
roots, ausschluss = lauf.roots_aus_db(eng)
print(f"{matnr} {kurztext.get(matnr, '')}")
print(f"Stichtag {src.stichtag}, Regelstand {regeln.version}, Lauf-Marker {sorted(src.marker) or '–'}")
print("in root_material:", matnr in roots, "| in root_ausschluss:", matnr in ausschluss)
print("Stammdatenprüfung / D15:", aufl.root_pruefung(matnr) or "ok")

# %%
erg = aufl.loese_alle([matnr])
df = erg.df()
print(len(df), "Positionen:", erg.statistik()["status"])

# %% [markdown]
# ## Baum (ausgeschlossene Zweige eingeklappt)

# %%
if IM_NOTEBOOK:
    from IPython.display import HTML, display

    display(HTML(anzeige.baum_html(df, kurztext)))
else:
    print(anzeige.baum_text(df, kurztext=kurztext))

# %% [markdown]
# ## Rangentscheidung pro Stückliste (D2–D4)

# %%
zeilen = []
for (stlnr, _stlal), e in aufl._ebenen.items():
    for merkmal, kand in e.wahl.kandidaten.items():
        zeilen.append({
            "stlnr": stlnr, "merkmal": merkmal, "gewaehlt": e.wahl.gewaehlt.get(merkmal, "– (kein Rang)"),
            "kandidaten": ", ".join(f"{k['wert']}:{k['status'] or 'neu'}{'/' + str(k['rang']) if k['rang'] else ''}"
                                    for k in kand),
            "bmeng": e.bmeng, "marker": ", ".join(m for m in e.wahl.marker if m.endswith(":" + merkmal)),
        })  # fmt: skip
pd.DataFrame(zeilen)

# %% [markdown]
# ## Positionen mit Spur

# %%
df["spur_lesbar"] = df["spur"].map(anzeige.spur_lesbar)
df[["ebene", "stlnr", "posnr", "parent_matnr", "matnr", "menge_kum", "status", "grund", "spur_lesbar"]]

# %% [markdown]
# ## Offene Punkte dieses Materials

# %%
df[df["status"] == "manuell_prüfen"][["pfad", "grund"]]

# %% [markdown]
# ## Vollständige Spur einer Position
#
# `PFAD_ENDE` = Ende des Pfads, z. B. `"0050:10000005"` (Positionsnummer:Material).

# %%
PFAD_ENDE = df["pfad"].iloc[0].rsplit("/", 1)[-1] if len(df) else ""
for _, z in df[df["pfad"].str.endswith(PFAD_ENDE)].iterrows():
    print(z["pfad"])
    print(json.dumps(z["spur"], ensure_ascii=False, indent=2, default=str))
