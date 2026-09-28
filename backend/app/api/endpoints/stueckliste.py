"""Fachliche Endpunkte: Materialien, Stückliste mit Regel-Entwurf, Regeln, Auswirkung, Übernehmen, Review, Export.

Nur Durchreichen – die Logik steckt in `basis_bom.dienst` (dieselbe wie `basis-bom run`).
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import angemeldet
from app.services.datenstand import Datenstand
from basis_bom import export
from basis_bom.dienst import Dienst, Eingabefehler, Entwurf, Konflikt

router = APIRouter(dependencies=[Depends(angemeldet)])


class NichtBereit(Exception):
    pass


NICHT_BEREIT_TEXT = {
    "laedt": "Die Daten werden gerade geladen – bitte kurz warten.",
    "leer": "Es sind noch keine SAP-Daten geladen.",
    "fehler": "Das Laden der Daten ist fehlgeschlagen – siehe Datenstand.",
}


def datenstand(request: Request) -> Datenstand:
    return request.app.state.datenstand


def dienst(ds: Datenstand = Depends(datenstand)) -> Dienst:
    if not ds.bereit:
        raise NichtBereit(NICHT_BEREIT_TEXT.get(ds.status.zustand, NICHT_BEREIT_TEXT["laedt"]))
    return ds.dienst


def fehler_antwort(exc: Exception) -> JSONResponse:
    if isinstance(exc, Konflikt):
        return JSONResponse(status_code=409, content={"fehler": str(exc), "konflikte": exc.konflikte})
    if isinstance(exc, Eingabefehler):
        return JSONResponse(status_code=400, content={"fehler": str(exc)})
    if isinstance(exc, NichtBereit):
        return JSONResponse(status_code=503, content={"fehler": str(exc) or NICHT_BEREIT_TEXT["laedt"]})
    raise exc


class MitEntwurf(BaseModel):
    entwurf: dict | None = None


class Uebernahme(BaseModel):
    entwurf: dict
    von: str
    begruendung: str | None = None


class ReviewDaten(BaseModel):
    von: str
    urteile: dict[str, dict] = Field(default_factory=dict)
    ergaenzt: list[dict] = Field(default_factory=list)
    # Review-Stand, auf dem die Eingaben beruhen (Feld weglassen = ohne Konfliktprüfung, z. B. Skripte)
    stand: str | None = None


class Bestaetigung(BaseModel):
    von: str


class MerkmalName(BaseModel):
    merkmal: str
    text: str


class EntwurfDaten(BaseModel):
    name: str
    entwurf: dict


@router.get("/meta")
def meta(d: Dienst = Depends(dienst)):
    return d.meta()


@router.get("/materialien")
def materialien(q: str = "", d: Dienst = Depends(dienst)):
    return d.materialien(q)


@router.post("/material/{matnr}")
def material(matnr: str, body: MitEntwurf, d: Dienst = Depends(dienst)):
    return d.material(matnr, Entwurf.aus(body.entwurf))


@router.post("/regeln")
def regeln(body: MitEntwurf, q: str = "", nur_offen: bool = False, d: Dienst = Depends(dienst)):
    return d.regeln(q, nur_offen, Entwurf.aus(body.entwurf))


@router.post("/auswirkung")
def auswirkung(body: MitEntwurf, d: Dienst = Depends(dienst)):
    return d.auswirkung(Entwurf.aus(body.entwurf))


@router.post("/uebernehmen")
def uebernehmen(body: Uebernahme, d: Dienst = Depends(dienst)):
    return d.uebernehmen(Entwurf.aus(body.entwurf), body.von, body.begruendung)


@router.post("/review/{matnr}")
def review(matnr: str, body: ReviewDaten, d: Dienst = Depends(dienst)):
    return d.review_speichern(matnr, body.urteile, body.ergaenzt, body.von, body.stand,
                              pruefe_stand="stand" in body.model_fields_set)  # fmt: skip


@router.post("/bestaetigen/{matnr}")
def bestaetigen(matnr: str, body: Bestaetigung, d: Dienst = Depends(dienst)):
    return d.bestaetigen(matnr, body.von)


@router.delete("/bestaetigen/{matnr}")
def bestaetigung_aufheben(matnr: str, d: Dienst = Depends(dienst)):
    d.bestaetigung_aufheben(matnr)
    return {"ok": True}


@router.get("/materialinfo/{matnr}")
def materialinfo(matnr: str, d: Dienst = Depends(dienst)):
    return d.material_info(matnr)


@router.get("/entwurf")
def entwurf_laden(name: str, d: Dienst = Depends(dienst)):
    return {"entwurf": d.entwurf_laden(name)}


@router.put("/entwurf")
def entwurf_speichern(body: EntwurfDaten, d: Dienst = Depends(dienst)):
    d.entwurf_speichern(body.name, body.entwurf)
    return {"ok": True}


@router.put("/merkmalname")
def merkmalname(body: MerkmalName, d: Dienst = Depends(dienst)):
    d.merkmal_name_setzen(body.merkmal, body.text)
    d.cache_leeren()
    return {"ok": True}


@router.get("/export/{matnr}")
def export_material(matnr: str, d: Dienst = Depends(dienst)):
    """Basis-Stückliste eines Materials im SAP-Format (D19) nach dem übernommenen Regelstand."""
    matnr = matnr.strip().lstrip("0")
    erg = d.aufloeser().loese_alle([matnr])
    if erg.uebersprungen:
        raise Eingabefehler(f"{matnr} kann nicht aufgelöst werden: {erg.uebersprungen[0]['grund']}")
    df = export.sap_format(erg.df(), d.src)
    puffer = io.StringIO()
    df.to_csv(puffer, index=False, sep=";", lineterminator="\n")
    daten = ("﻿" + puffer.getvalue()).encode("utf-8")  # BOM: Excel erkennt UTF-8 und Umlaute
    return StreamingResponse(
        io.BytesIO(daten), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{matnr}_sap_format.csv"'},
    )  # fmt: skip


# ---------------------------------------------------------------------------------------------------- Datenstand


@router.get("/datenstand")
def datenstand_info(ds: Datenstand = Depends(datenstand)):
    return ds.info()


@router.post("/datenstand/neu-laden")
def datenstand_neu_laden(ds: Datenstand = Depends(datenstand)):
    try:
        gestartet = ds.starte("exporte")
    except FileNotFoundError as exc:
        raise Eingabefehler(str(exc)) from None
    if not gestartet:
        raise Eingabefehler("Es läuft bereits ein Ladevorgang.")
    return ds.info()
