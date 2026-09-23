"""Prototyp-Lauf nach D23: Konsistenzprüfungen → Auflösung → Regression (meldet nur) → Export.

Prod-Betrieb (Node-RED-Trigger, harte Regression, Betriebs-Dockerfile) ist bewusst nicht Teil des Prototyps.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from . import checks, config, export, lauf, regress, review
from .source import SapSource

log = logging.getLogger(__name__)


@dataclass
class Laufbericht:
    lauf_id: int
    pruefungen: pd.DataFrame
    statistik: dict
    regression: pd.DataFrame
    dateien: list[Path] = field(default_factory=list)
    sekunden: dict[str, float] = field(default_factory=dict)


def run(
    eng: Engine, matnr: Iterable[str] | None = None, out: Path | None = None, review_blaetter: bool = True
):
    t0 = time.perf_counter()
    zeiten: dict[str, float] = {}
    pr = checks.pruefe(eng)
    zeiten["check"] = time.perf_counter() - t0
    rot = pr[pr["ok"] == False]  # noqa: E712
    if not rot.empty:
        log.warning("%s Prüfungen rot – Prototyp läuft weiter (D23: Regression/Checks melden nur)", len(rot))

    t = time.perf_counter()
    lauf_id, erg = lauf.fuehre_aufloesung_aus(eng, list(matnr) if matnr else None)
    zeiten["aufloesung"] = time.perf_counter() - t

    t = time.perf_counter()
    reg = regress.regress(eng, lauf_id)
    zeiten["regression"] = time.perf_counter() - t

    t = time.perf_counter()
    ziel = (out or config.out_dir()) / f"lauf_{lauf_id}"
    df = erg.df()
    src = SapSource.from_db(eng)
    dateien = export.exportiere(df, src, ziel)
    if review_blaetter:
        stat = lauf.lade_statistik(eng, lauf_id)
        for root in sorted(set(df["root_matnr"])):
            dateien.append(
                review.review_blatt(df, src, lauf_id, root, stat, ziel / root / f"review_{root}.xlsx")
            )
    zeiten["export"] = time.perf_counter() - t
    zeiten["gesamt"] = time.perf_counter() - t0
    lauf.beende_lauf(
        eng, lauf_id, lauf.lauf_status(eng, lauf_id), {"sekunden": zeiten, "checks_rot": len(rot)}
    )
    return Laufbericht(lauf_id, pr, erg.statistik(), reg, dateien, zeiten)
