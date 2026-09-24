"""Lesezugriff auf `sap_raw` mit Stichtag (D14) und Ersatzregeln (EXPORT-PLAN „Übergang“).

Gültigkeit (D14): Stichtag = Exportdatum. Zeilen mit `DATUV` > Stichtag existieren nicht. Bei versionierten
Objekten gilt die neueste Version mit `DATUV` ≤ Stichtag (bei CUKB zusätzlich `KNSTA` = freigegeben);
ist diese gelöscht (`LKENZ`), existiert das Objekt nicht. Siehe docs/FRAGEN.md zu dieser Lesart.
"""

from __future__ import annotations

import datetime as dt
import logging
from functools import cached_property

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from . import config, headers

log = logging.getLogger(__name__)

# CUKB-Domänen (Annahmen, docs/FRAGEN.md): KNSTA 1 = freigegeben; KNART 5 = Auswahlbedingung, 7 = Prozedur.
KNSTA_FREIGEGEBEN = {"1"}
KNART_AUSWAHL = {"5"}
KNART_PROZEDUR = {"7"}

# Versionierte Objekte: Schlüssel und Versionszähler.
VERSIONEN: dict[str, tuple[list[str], str | None, list[str]]] = {
    "STPO": (["STLNR", "STLKN"], "STPOZ", ["LKENZ"]),
    "STAS": (["STLNR", "STLAL", "STLKN"], "STASZ", ["LKENZ"]),
    "STKO": (["STLNR", "STLAL"], "STKOZ", ["LKENZ", "LOEKZ"]),
    "CUOB": (["KNOBJ", "KNNUM"], None, ["LKENZ"]),
    "CUKB": (["KNNUM"], "ADZHL", ["LKENZ"]),
    "CUKBT": (["KNNUM"], "ADZHL", ["LKENZ"]),
}


class StichtagFehler(ValueError):
    pass


def _gesetzt(s: pd.Series) -> pd.Series:
    return s.notna() & (s.astype(str).str.strip() != "")


def bis_stichtag(datuv: pd.Series, stichtag: dt.date) -> pd.Series:
    """D14: ohne DATUV oder DATUV ≤ Stichtag. Robust gegen date-, datetime- und reine NaT-Spalten."""
    ts = pd.to_datetime(datuv, errors="coerce")
    return ts.isna() | (ts <= pd.Timestamp(stichtag))


def neueste_version(
    df: pd.DataFrame, stichtag: dt.date, keys: list[str], zaehler: str | None, loesch: list[str]
) -> pd.DataFrame:
    """D14: `DATUV` ≤ Stichtag, pro Schlüssel neueste Version (DATUV, Zähler), gelöschte entfallen."""
    if df.empty:
        return df
    d = df
    if "DATUV" in d.columns:
        d = d[bis_stichtag(d["DATUV"], stichtag)]
    keys = [k for k in keys if k in d.columns]
    if keys:
        sortcols, tmp = [], d.copy()
        if "DATUV" in tmp.columns:
            tmp["_datuv"] = pd.to_datetime(tmp["DATUV"]).fillna(pd.Timestamp.min)
            sortcols.append("_datuv")
        if zaehler and zaehler in tmp.columns:
            tmp["_zaehler"] = pd.to_numeric(tmp[zaehler], errors="coerce").fillna(0)
            sortcols.append("_zaehler")
        if sortcols:
            tmp = tmp.sort_values(sortcols, kind="stable")
        d = tmp.groupby(keys, sort=False, dropna=False).tail(1).drop(columns=["_datuv", "_zaehler"],
                                                                       errors="ignore")  # fmt: skip
    for col in loesch:
        if col in d.columns:
            d = d[~_gesetzt(d[col])]
    return d.sort_index()


class SapSource:
    """Liefert jede benötigte Tabelle als DataFrame, gefiltert nach D14, mit Ersatzmarkern."""

    def __init__(
        self,
        tabellen: dict[str, pd.DataFrame],
        export_daten: dict[str, dt.date],
        stichtag: dt.date | None = None,
        prod: bool | None = None,
    ) -> None:
        self._roh = {k.upper(): v for k, v in tabellen.items()}
        self._ersatz_marker: set[str] = set()
        for tab in ("MAST", "STKO", "STAS"):  # ohne STLAL: eine Alternative „1“ annehmen
            if tab in self._roh and "STLAL" not in self._roh[tab].columns:
                self._roh[tab] = self._roh[tab].assign(STLAL="1")
                self._ersatz_marker.add(f"stlal_fehlt:{tab}")
        self._stas_nutzbar = "STAS" in self._roh and "STLKN" in self._roh["STAS"].columns
        if "STAS" in self._roh and not self._stas_nutzbar:
            log.warning("STAS ohne STLKN – STAS wird nicht verwendet (Marker stas_fehlt)")
        self.export_daten = dict(export_daten)
        self.warnungen: list[str] = []
        self.marker: set[str] = set()
        prod = config.prod_mode() if prod is None else prod
        daten = sorted(set(self.export_daten.values()))
        if len(daten) > 1:
            text = "abweichende export_datum: " + ", ".join(
                f"{t}={d}" for t, d in sorted(self.export_daten.items())
            )
            if prod:
                raise StichtagFehler(text)
            self.warnungen.append(text + f" – Lauf-Stichtag = jüngstes Datum {daten[-1]} (Dev-Daten)")
            log.warning(self.warnungen[-1])
        self.stichtag = stichtag or (daten[-1] if daten else dt.date.today())
        self._pruefe_ersatz()

    # -----------------------------------------------------------------------------------------------------
    @classmethod
    def from_db(cls, eng: Engine, stichtag: dt.date | None = None, prod: bool | None = None) -> SapSource:
        tabellen, daten = {}, {}
        with eng.connect() as con:
            for tab in headers.SPALTEN:
                if (
                    con.execute(sa.text("SELECT to_regclass(:n)"), {"n": f"sap_raw.{tab.lower()}"}).scalar()
                    is None
                ):
                    continue
                df = pd.read_sql_table(tab.lower(), con, schema="sap_raw")
                df.columns = [c.upper() for c in df.columns]
                ed = df.pop("EXPORT_DATUM") if "EXPORT_DATUM" in df.columns else None
                if ed is not None and ed.notna().any():
                    daten[tab] = pd.to_datetime(ed.dropna().iloc[0]).date()
                for col in df.columns:
                    if col == "DATUV":
                        df[col] = pd.to_datetime(df[col], errors="coerce")
                    elif col in {"MENGE", "BMENG"}:
                        df[col] = pd.to_numeric(df[col])
                    else:
                        df[col] = df[col].fillna("").astype(str)
                tabellen[tab] = df
        return cls(tabellen, daten, stichtag, prod)

    @classmethod
    def from_ladeergebnis(cls, erg, stichtag: dt.date | None = None, prod: bool | None = None) -> SapSource:
        return cls(erg.tabellen, erg.export_daten, stichtag, prod)

    # -----------------------------------------------------------------------------------------------------
    def hat(self, tab: str) -> bool:
        return tab in self._roh

    def roh(self, tab: str) -> pd.DataFrame:
        return self._roh[tab]

    def _pruefe_ersatz(self) -> None:
        self.marker |= self._ersatz_marker
        for tab in ("MAST", "STPO", "CUOB", "CUKB"):
            if tab not in self._roh:
                raise ValueError(f"{tab} fehlt in sap_raw – ohne diese Tabelle keine Auflösung")
        if "STKO" not in self._roh:
            self.marker.add("bmeng_angenommen")
        if not self._stas_nutzbar:
            self.marker.add("stas_fehlt")
        if "CABN" not in self._roh or "CAWN" not in self._roh:
            self.marker.add("cawn_fehlt")
        if "MAKT" not in self._roh:
            self.marker.add("makt_fehlt")
        if "MARA" not in self._roh:
            self.marker.add("mara_fehlt")
        if "MARC" not in self._roh:
            self.marker.add("marc_fehlt")
        cukb = self._roh["CUKB"]
        if "KNART" not in cukb.columns or not _gesetzt(cukb["KNART"]).any():
            self.marker.add("knart_fehlt")  # D10: alle Beziehungen als Auswahlbedingungen
        if "KNSTA" not in cukb.columns or not _gesetzt(cukb["KNSTA"]).any():
            self.marker.add("knsta_fehlt")

    def _versioniert(self, tab: str) -> pd.DataFrame:
        keys, zaehler, loesch = VERSIONEN[tab]
        return neueste_version(self._roh[tab], self.stichtag, keys, zaehler, loesch)

    # -----------------------------------------------------------------------------------------------------
    @cached_property
    def mast(self) -> pd.DataFrame:
        """Werk 4000, Verwendung 1; `LKENZ` gesetzt → nicht Teil von S (EXPORT-PLAN Phase 1)."""
        d = self._roh["MAST"]
        d = d[(d["WERKS"] == config.WERKS) & (d["STLAN"] == config.STLAN)]
        if "LKENZ" in d.columns:
            d = d[~_gesetzt(d["LKENZ"])]
        if "DATUV" in d.columns:
            d = d[bis_stichtag(d["DATUV"], self.stichtag)]
        return d

    @cached_property
    def stlnr_pro_material(self) -> dict[str, list[tuple[str, str]]]:
        """MATNR → [(STLNR, STLAL)], sortiert. Mehr als ein STLNR ist ein D15-Verstoß."""
        out: dict[str, list[tuple[str, str]]] = {}
        stlal = self.mast["STLAL"] if "STLAL" in self.mast.columns else pd.Series("1", index=self.mast.index)
        for matnr, stlnr, alt in zip(self.mast["MATNR"], self.mast["STLNR"], stlal, strict=True):
            out.setdefault(matnr, [])
            if (stlnr, alt) not in out[matnr]:
                out[matnr].append((stlnr, alt))
        return {k: sorted(v, key=lambda x: (x[0], x[1].zfill(3))) for k, v in out.items()}

    @cached_property
    def stpo(self) -> pd.DataFrame:
        return self._versioniert("STPO")

    @cached_property
    def stas(self) -> pd.DataFrame | None:
        return self._versioniert("STAS") if self._stas_nutzbar else None

    @cached_property
    def stko(self) -> pd.DataFrame | None:
        return self._versioniert("STKO") if "STKO" in self._roh else None

    @cached_property
    def cuob(self) -> pd.DataFrame:
        d = self._roh["CUOB"]
        if "KNTAB" in d.columns:
            d = d[d["KNTAB"] == "STPO"]
        return neueste_version(d, self.stichtag, *VERSIONEN["CUOB"])

    @cached_property
    def cukb(self) -> pd.DataFrame:
        d = self._roh["CUKB"]
        if "knsta_fehlt" not in self.marker:
            d = d[d["KNSTA"].isin(KNSTA_FREIGEGEBEN)]
        return neueste_version(d, self.stichtag, *VERSIONEN["CUKB"])

    @cached_property
    def cukbt(self) -> pd.DataFrame | None:
        return self._versioniert("CUKBT") if "CUKBT" in self._roh else None

    @cached_property
    def mara(self) -> pd.DataFrame | None:
        return self._roh.get("MARA")

    @cached_property
    def marc(self) -> pd.DataFrame | None:
        d = self._roh.get("MARC")
        return None if d is None else d[d["WERKS"] == config.WERKS]

    @cached_property
    def makt(self) -> pd.DataFrame | None:
        return self._roh.get("MAKT")

    @cached_property
    def cabn(self) -> pd.DataFrame | None:
        return self._roh.get("CABN")

    @cached_property
    def cawn(self) -> pd.DataFrame | None:
        return self._roh.get("CAWN")

    # -----------------------------------------------------------------------------------------------------
    # Lookups für die Auflösung

    @cached_property
    def positionen(self) -> dict[str, pd.DataFrame]:
        """STLNR → gültige STPO-Zeilen, sortiert nach POSNR/STLKN."""
        d = self.stpo.copy()
        d["_pos"] = d["POSNR"].str.zfill(6) if "POSNR" in d.columns else ""
        d["_kn"] = pd.to_numeric(d["STLKN"], errors="coerce")
        d = d.sort_values(["STLNR", "_pos", "_kn"], kind="stable").drop(columns=["_pos", "_kn"])
        return {k: g for k, g in d.groupby("STLNR", sort=False)}

    @cached_property
    def _stas_stlnr(self) -> set[str]:
        return set(self._roh["STAS"]["STLNR"]) if self._stas_nutzbar else set()

    def positionen_fuer(self, stlnr: str, stlal: str) -> pd.DataFrame:
        """Positionen einer Stückliste; hat STAS Einträge für die Stückliste, nur die gültigen Knoten der
        Alternative (neueste STAS-Version ≤ Stichtag, nicht gelöscht – D14)."""
        pos = self.positionen.get(stlnr, self.stpo.iloc[0:0])
        if self.stas is not None and stlnr in self._stas_stlnr:
            st = self.stas
            knoten = set(st.loc[(st["STLNR"] == stlnr) & (st["STLAL"] == stlal), "STLKN"])
            pos = pos[pos["STLKN"].isin(knoten)]
        return pos

    def bmeng(self, stlnr: str, stlal: str) -> tuple[float, bool]:
        """Basismenge (D17); fehlt STKO oder die Zeile → 1 mit Marker `bmeng_angenommen`."""
        if self.stko is not None:
            z = self.stko[(self.stko["STLNR"] == stlnr) & (self.stko["STLAL"] == stlal)]
            if z.empty:
                z = self.stko[self.stko["STLNR"] == stlnr]
            if not z.empty and pd.notna(z.iloc[-1]["BMENG"]) and float(z.iloc[-1]["BMENG"]) != 0:
                return float(z.iloc[-1]["BMENG"]), False
        return 1.0, True

    @cached_property
    def knnum_pro_knobj(self) -> dict[str, list[str]]:
        d = self.cuob.copy()
        if "KNSRT" in d.columns:
            d["_s"] = pd.to_numeric(d["KNSRT"], errors="coerce")
            d = d.sort_values(["KNOBJ", "_s", "KNNUM"], kind="stable")
        return d.groupby("KNOBJ", sort=False)["KNNUM"].apply(list).to_dict()

    @cached_property
    def knobj_roh(self) -> set[str]:
        """KNOBJ mit irgendeiner CUOB-Zeile (auch gelöscht) – unterscheidet „gelöscht“ von „fehlt im Export“."""
        return set(self._roh["CUOB"]["KNOBJ"])

    @cached_property
    def beziehungen(self) -> dict[str, dict]:
        """KNNUM → {knnam, knart, adzhl} der gültigen CUKB-Version."""
        d = self.cukb
        knart = d["KNART"] if "KNART" in d.columns else pd.Series("", index=d.index)
        adzhl = d["ADZHL"] if "ADZHL" in d.columns else pd.Series("", index=d.index)
        return {
            k: {"knnam": n, "knart": a, "adzhl": z}
            for k, n, a, z in zip(d["KNNUM"], d["KNNAM"], knart, adzhl, strict=True)
        }

    @cached_property
    def knnum_roh(self) -> set[str]:
        return set(self._roh["CUKB"]["KNNUM"])

    def lookup(self, tab: str, spalte: str) -> dict[str, str]:
        d = {"MARA": self.mara, "MARC": self.marc, "MAKT": self.makt}[tab]
        if d is None or spalte not in d.columns:
            return {}
        return d.drop_duplicates("MATNR").set_index("MATNR")[spalte].to_dict()
