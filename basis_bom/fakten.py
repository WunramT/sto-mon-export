"""Offene Fakten F1–F6 (docs/DECISIONS.md) als Zahlen – Grundlage für Notebook 00 und docs/FRAGEN.md."""

from __future__ import annotations

import re

import pandas as pd

from .source import SapSource

NEGATION = re.compile(r"<>|!=|\bNICHT\b|\bNOT\b|\bOHNE\b", re.I)


def f1_cukb_mehrfach(src: SapSource) -> pd.DataFrame:
    """F1: KNNUM mit mehreren CUKB-Zeilen und ob sich ADZHL/AENNR/DATUV unterscheiden."""
    d = src.roh("CUKB")
    g = d.groupby("KNNUM")
    mehr = g.size()
    mehr = mehr[mehr > 1]
    zeilen = []
    for knnum in mehr.index:
        grp = d[d["KNNUM"] == knnum]
        zeilen.append(
            {
                "KNNUM": knnum,
                "zeilen": len(grp),
                **{
                    f"{c}_verschieden": grp[c].nunique() > 1
                    for c in ("ADZHL", "AENNR", "DATUV", "KNNAM")
                    if c in grp.columns
                },  # fmt: skip
            }
        )
    return pd.DataFrame(zeilen)


def f2_negationen(src: SapSource) -> pd.DataFrame:
    namen = pd.Series(sorted(set(src.roh("CUKB")["KNNAM"])))
    return pd.DataFrame({"KNNAM": namen[namen.str.contains(NEGATION)]})


def f3_alternativpositionen(src: SapSource) -> pd.DataFrame:
    d = src.stpo
    return pd.DataFrame(
        {
            spalte: [int((d[spalte].astype(str).str.strip() != "").sum()) if spalte in d.columns else None]
            for spalte in ("ALPGR", "ALPRF")
        }
        | {"positionen": [len(d)]}
    )


def f4_knart_verteilung(src: SapSource) -> pd.DataFrame:
    """F4: KNART der Beziehungen, die an gültigen STPO-Positionen hängen."""
    knobj = set(src.stpo["KNOBJ"]) - {"", "0"}
    knnum = {n for k in knobj for n in src.knnum_pro_knobj.get(k, [])}
    cukb = src.cukb[src.cukb["KNNUM"].isin(knnum)]
    if "KNART" not in cukb.columns:
        return pd.DataFrame({"KNART": ["(Spalte fehlt)"], "anzahl": [len(cukb)]})
    return cukb["KNART"].replace("", "(leer)").value_counts().rename_axis("KNART").reset_index(name="anzahl")


def f5_mehrere_stlnr(src: SapSource) -> pd.DataFrame:
    zeilen = [
        {"MATNR": m, "STLNR": ", ".join(s for s, _ in v), "anzahl": len({s for s, _ in v})}
        for m, v in src.stlnr_pro_material.items()
        if len({s for s, _ in v}) > 1
    ]
    return pd.DataFrame(zeilen, columns=["MATNR", "STLNR", "anzahl"])


def f6_bmeng(src: SapSource) -> pd.DataFrame:
    if src.stko is None:
        return pd.DataFrame({"hinweis": ["STKO fehlt – BMENG = 1 angenommen (bmeng_angenommen)"]})
    d = src.stko
    ungleich = d[d["BMENG"].fillna(1) != 1]
    return pd.DataFrame(
        {
            "stuecklisten": [d["STLNR"].nunique()],
            "bmeng_ungleich_1": [ungleich["STLNR"].nunique()],
            "anteil": [ungleich["STLNR"].nunique() / max(d["STLNR"].nunique(), 1)],
        }  # fmt: skip
    )


def uebersicht(src: SapSource) -> pd.DataFrame:
    f1, f2, f3, f4 = (
        f1_cukb_mehrfach(src),
        f2_negationen(src),
        f3_alternativpositionen(src),
        f4_knart_verteilung(src),
    )
    f5, f6 = f5_mehrere_stlnr(src), f6_bmeng(src)
    prozeduren = int(f4.loc[f4["KNART"].isin(["7"]), "anzahl"].sum()) if "KNART" in f4 else 0
    return pd.DataFrame(
        [
            ("F1", "KNNUM mit >1 CUKB-Zeile", len(f1)),
            ("F2", "Bedingungsnamen mit Negation", len(f2)),
            ("F3", "STPO-Positionen mit ALPGR", int(f3["ALPGR"].iloc[0] or 0)),
            ("F4", "Beziehungen an STPO mit KNART=7 (Prozedur)", prozeduren),
            ("F4", "Beziehungen an STPO gesamt", int(f4["anzahl"].sum())),
            ("F5", "Materialien mit >1 STLNR (D15)", len(f5)),
            (
                "F6",
                "Stücklisten mit BMENG ≠ 1",
                int(f6["bmeng_ungleich_1"].iloc[0]) if "bmeng_ungleich_1" in f6 else None,
            ),
        ],
        columns=["fakt", "frage", "wert"],
    )
