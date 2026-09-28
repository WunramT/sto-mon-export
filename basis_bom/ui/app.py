"""FastAPI-App der Web-Oberfläche (`basis-bom ui`). Nur Durchreichen – die Logik steckt in dienst.py."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from .dienst import Dienst, Eingabefehler, Entwurf, Konflikt

STATIC = Path(__file__).parent / "static"


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


class Bestaetigung(BaseModel):
    von: str


def erstelle_app(eng: Engine) -> FastAPI:
    app = FastAPI(title="Basis-Stückliste", docs_url=None, redoc_url=None)
    dienst = Dienst(eng)
    app.state.dienst = dienst

    def fehler(exc: Exception):
        if isinstance(exc, Konflikt):
            return JSONResponse(status_code=409, content={"fehler": str(exc), "konflikte": exc.konflikte})
        if isinstance(exc, Eingabefehler):
            return JSONResponse(status_code=400, content={"fehler": str(exc)})
        raise exc

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/meta")
    def meta():
        return dienst.meta()

    @app.get("/api/materialien")
    def materialien(q: str = ""):
        return dienst.materialien(q)

    @app.post("/api/material/{matnr}")
    def material(matnr: str, body: MitEntwurf):
        try:
            return dienst.material(matnr, Entwurf.aus(body.entwurf))
        except (Eingabefehler, Konflikt) as exc:
            return fehler(exc)

    @app.post("/api/regeln")
    def regeln(body: MitEntwurf, q: str = "", nur_offen: bool = False):
        return dienst.regeln(q, nur_offen, Entwurf.aus(body.entwurf))

    @app.post("/api/auswirkung")
    def auswirkung(body: MitEntwurf):
        return dienst.auswirkung(Entwurf.aus(body.entwurf))

    @app.post("/api/uebernehmen")
    def uebernehmen(body: Uebernahme):
        try:
            return dienst.uebernehmen(Entwurf.aus(body.entwurf), body.von, body.begruendung)
        except (Eingabefehler, Konflikt) as exc:
            return fehler(exc)

    @app.post("/api/review/{matnr}")
    def review(matnr: str, body: ReviewDaten):
        try:
            return dienst.review_speichern(matnr, body.urteile, body.ergaenzt, body.von)
        except Eingabefehler as exc:
            return fehler(exc)

    @app.post("/api/bestaetigen/{matnr}")
    def bestaetigen(matnr: str, body: Bestaetigung):
        try:
            return dienst.bestaetigen(matnr, body.von)
        except Eingabefehler as exc:
            return fehler(exc)

    @app.post("/api/neu-laden")
    def neu_laden():
        dienst.neu_laden()
        return {"ok": True}

    @app.exception_handler(HTTPException)
    def http_fehler(_req, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"fehler": exc.detail})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
