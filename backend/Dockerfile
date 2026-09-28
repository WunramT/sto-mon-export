# Backend: FastAPI + Fachlogik basis_bom. Build-Kontext ist das Repo-Wurzelverzeichnis (siehe .gitlab-ci.yml).
FROM python:3.13-slim AS builder

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.13-slim

WORKDIR /app

RUN useradd -m -u 1000 appuser \
    && mkdir -p /data/exports /data/out && chown appuser:appuser /data/out

COPY --from=builder /root/.local /home/appuser/.local

# Anwendung (app/) und Fachlogik mit ihren Daten-Dateien: basis_bom/config.py erwartet sql/, legacy/ und
# tests/fixtures/ (Beispieldaten für DEMO_FIXTURES) neben dem Paket.
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/entrypoint.sh ./entrypoint.sh
COPY basis_bom ./basis_bom
COPY sql ./sql
COPY legacy ./legacy
COPY tests/fixtures ./tests/fixtures

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    EXPORTS_DIR=/data/exports \
    OUT_DIR=/data/out \
    BASIS_BOM_OUT=/data/out \
    BASIS_BOM_FRAGEN=/data/out/FRAGEN.md

RUN chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app /home/appuser/.local

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5).status == 200 else 1)"

CMD ["/app/entrypoint.sh"]
