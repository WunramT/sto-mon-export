"""Anmeldung mit dem gemeinsamen Passwort: kurzlebiges JWT (HS256) für alle API-Aufrufe."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

ALGORITHMUS = "HS256"
_bearer = HTTPBearer(auto_error=False)


def passwort_ok(passwort: str) -> bool:
    soll = settings.master_password_admin
    return bool(soll) and hmac.compare_digest(passwort.encode(), soll.encode())


def erstelle_token() -> tuple[str, int]:
    dauer = settings.access_token_expire_minutes * 60
    jetzt = datetime.now(UTC)
    token = jwt.encode({"sub": "team", "rolle": "admin", "iat": jetzt, "exp": jetzt + timedelta(seconds=dauer)},
                       settings.secret_key, algorithm=ALGORITHMUS)  # fmt: skip
    return token, dauer


def angemeldet(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    """Abhängigkeit für alle geschützten Endpunkte."""
    if not settings.auth_aktiv:
        return
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bitte anmelden.")
    try:
        jwt.decode(cred.credentials, settings.secret_key, algorithms=[ALGORITHMUS])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sitzung abgelaufen – bitte neu anmelden.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bitte anmelden.") from None
