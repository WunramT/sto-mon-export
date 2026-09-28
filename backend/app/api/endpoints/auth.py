"""Anmeldung mit dem gemeinsamen Team-Passwort (Prototyp: alle haben alle Rechte)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.core.security import angemeldet, erstelle_token, passwort_ok

router = APIRouter(prefix="/auth")


class Login(BaseModel):
    passwort: str


@router.get("/config")
def auth_config():
    return {"auth_aktiv": settings.auth_aktiv, "app_name": settings.app_name, "version": settings.app_version}


@router.post("/login")
def login(body: Login):
    if not settings.auth_aktiv:
        token, dauer = erstelle_token()
        return {"access_token": token, "token_type": "bearer", "expires_in": dauer}
    if not passwort_ok(body.passwort):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Das Passwort stimmt nicht.")
    token, dauer = erstelle_token()
    return {"access_token": token, "token_type": "bearer", "expires_in": dauer}


@router.get("/pruefen", dependencies=[Depends(angemeldet)])
def pruefen():
    return {"ok": True}
