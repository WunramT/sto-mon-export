#!/bin/sh
set -e
# Schema, Laden der Exporte und Vorberechnung laufen im Backend selbst (Hintergrund, siehe app/services/datenstand.py).
# Ein Worker: der Datenstand (Cache der aufgelösten Stücklisten) liegt im Prozess.
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 \
    --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30
