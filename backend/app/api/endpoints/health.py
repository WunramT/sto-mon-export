from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    """Liveness für Docker/Jenkins: gesund, sobald der Prozess läuft – auch während die Daten laden."""
    ds = getattr(request.app.state, "datenstand", None)
    return {"status": "ok", "daten": ds.status.zustand if ds else None}
