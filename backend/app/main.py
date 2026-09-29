"""FastAPI-Anwendung: Export konfigurierbare Stücklisten (Basis-Stückliste, Prototyp)."""

from __future__ import annotations

import faulthandler
import logging
import signal
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from starlette.exceptions import HTTPException

from app.api.endpoints.stueckliste import NichtBereit, fehler_antwort
from app.api.router import api_router
from app.config import settings
from app.services.datenstand import Datenstand
from basis_bom import db
from basis_bom.dienst import Eingabefehler, Konflikt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Betrieb: `docker kill -s USR1 <backend>` schreibt die Stacks aller Threads ins Log (wo hängt/rechnet es gerade?)
if hasattr(signal, "SIGUSR1"):
    faulthandler.register(signal.SIGUSR1, all_threads=True)
log = logging.getLogger("app")


def create_app(eng: Engine | None = None, *, starte_laden: bool = True) -> FastAPI:
    settings.pruefe()
    eng = eng or db.engine(settings.database_url)
    ds = Datenstand(eng, settings.exports_dir, settings.out_dir, settings.demo_fixtures)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info("Starte %s %s (MODE=%s, Anmeldung %s)", settings.app_name, settings.app_version, settings.mode,
                 "aktiv" if settings.auth_aktiv else "aus")  # fmt: skip
        if starte_laden:
            # Nicht blockieren: Health-Check muss sofort antworten, auch wenn Schema/Vorberechnung dauern
            threading.Thread(target=_start_sicher, args=(ds,), name="datenstand-start", daemon=True).start()
        yield

    app = FastAPI(
        title=settings.app_name, version=settings.app_version, root_path=settings.root_path,
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json", lifespan=lifespan,
    )  # fmt: skip
    app.state.datenstand = ds
    if settings.cors_origins_list:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])  # fmt: skip

    @app.exception_handler(Konflikt)
    @app.exception_handler(Eingabefehler)
    @app.exception_handler(NichtBereit)
    def fachfehler(_req: Request, exc: Exception):
        return fehler_antwort(exc)

    @app.exception_handler(HTTPException)
    def http_fehler(_req: Request, exc: HTTPException):
        text = exc.detail if isinstance(exc.detail, str) else "Fehler"
        if exc.status_code == 404 and text == "Not Found":
            text = "Nicht gefunden"
        elif exc.status_code == 405:
            text = "Methode nicht erlaubt"
        kopf = getattr(exc, "headers", None)
        return JSONResponse(status_code=exc.status_code, content={"fehler": text}, headers=kopf)

    @app.exception_handler(RequestValidationError)
    def eingabe_ungueltig(_req: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"fehler": "Ungültige Eingabe", "details": exc.errors()})

    app.include_router(api_router, prefix="/api")
    return app


def _start_sicher(ds: Datenstand) -> None:
    try:
        ds.beim_start()
    except Exception as exc:  # noqa: BLE001 - z. B. Datenbank nicht erreichbar: in der Oberfläche anzeigen
        log.exception("Start fehlgeschlagen")
        from app.api.endpoints.health import db_fehlertext

        ds.status.zustand = "fehler"
        ds.status.fehler = db_fehlertext(exc)

