# Export konfigurierbare Stücklisten – Basis-Stückliste (Prototyp)

Leitet aus SAP-Exporttabellen (Werk 4000, Verwendung 1) die Basis-Version konfigurierbarer Stücklisten ab.
Regeln: `docs/DECISIONS.md`. Plan: `docs/AGENT-PLAN.md`. Offene Fragen und Annahmen: `docs/FRAGEN.md`.

## Start

**Web-Anwendung** (für den Fachbereich): Vue/Vuetify-Oberfläche (`frontend/`) + FastAPI-Backend (`backend/`), das
die Fachlogik `basis_bom` direkt nutzt. Anmeldung mit einem gemeinsamen Team-Passwort; jede:r trägt den eigenen Namen ein.

```bash
docker compose up --build        # http://localhost:3000, Passwort „test“, Beispieldaten (tests/fixtures)
EXPORTS_DIR=/pfad/zu/exporten docker compose up   # mit echten Exporten (docs/EXPORTE.md)
```

Deployment auf einen Host per GitLab CI (Images) + Jenkins (Deploy): **`docs/DEPLOYMENT.md`**.

**Entwicklung** – VS Code → *Reopen in Container*. Der Devcontainer startet Postgres, installiert das Paket, registriert
den Jupyter-Kernel `basis-bom` und lädt die Fixtures. Echte Exporte liegen außerhalb des Repos; Pfad in
`.devcontainer/.env` (`EXPORTS_DIR`, Vorlage `.env.example`), im Container unter `/data/exports`.

```bash
# Backend (Port 8000) und Frontend (Port 3000, Proxy /api → 8000)
cd backend && PYTHONPATH=.:.. SECRET_KEY=$(python -c 'print("x"*32)') MASTER_PASSWORD_ADMIN=test \
  DATABASE_HOST=db DATABASE_USER=basis DATABASE_PASSWORD=basis DATABASE_NAME=basis uvicorn app.main:create_app --factory --reload
cd frontend && npm install && VITE_BASE_PATH=/ VITE_PROXY_TARGET=http://localhost:8000 npm run dev

basis-bom db init --from-dir /data/exports   # maßgebliche Exporte laden (docs/EXPORTE.md), Prüfpunkte → docs/FRAGEN.md
basis-bom run --matnr 11071032 --matnr 11071089   # check → Auflösung → regress → Export
basis-bom check                                 # Konsistenz- und Exportprüfungen
basis-bom export [--lauf N] [--matnr …]         # SAP-Format (D19)
basis-bom regress [--lauf N]
basis-bom regel liste [MERKMAL] | regel setzen … | regel alias …
basis-bom sql "<SELECT …>" [--csv datei]
pytest                                          # Tests Fachlogik + API (eigene Datenbank <name>_test)
cd frontend && npm run lint && npm run type-check && npm run test:run   # Frontend
```

Ausgabe unter `out/lauf_<id>/<matnr>/`: `<matnr>_sap_format.csv`. Zur Begründung von
Urteilen: `notebooks/90_debug_material.ipynb` (Materialnummer eintragen, alles ausführen).

## Aufbau

| Pfad | Inhalt |
|---|---|
| `basis_bom/loader.py`, `headers.py` | Exporte lesen, Header mappen, beim Laden filtern (Schlüsselmengen) |
| `basis_bom/source.py` | Lesezugriff `sap_raw` mit Stichtag (D14), Ersatzmarker |
| `basis_bom/rules.py`, `parser.py`, `ranking.py` | Regelstand, Bedingungsnamen, Entscheidung pro Ebene |
| `basis_bom/explode.py`, `lauf.py`, `pipeline.py` | Auflösung mit Spur, Lauf speichern, Prototyp-Lauf |
| `basis_bom/export.py`, `regress.py` | SAP-Format, Regression |
| `basis_bom/dienst.py` | Logik der Web-Oberfläche: Material rechnen mit Regel-Entwurf, Auswirkung, Übernehmen, Review |
| `backend/` | FastAPI: Anmeldung (Team-Passwort, JWT), Endpunkte, Datenstand (Exporte im Hintergrund laden), Dockerfile |
| `frontend/` | Vue 3 + Vuetify + Pinia: Materialliste, Stücklistenbaum, Regeln, Auswirkung, Bewertung; nginx-Image |
| `Jenkinsfile`, `.gitlab-ci.yml`, `deploy/` | CI (Tests, Images nach Harbor) und Deployment auf einen Host (`docs/DEPLOYMENT.md`) |
| `sql/schema`, `sql/views`, `sql/checks` | DDL + Seeds, Reports, Prüfungen |
| `notebooks/` | jupytext-Paare (`.py` editieren, `.ipynb` öffnen) |
| `tests/` | Tests Fachlogik und API (`test_api.py`); `fixtures`, `golden`: synthetische Mini-SAP-Tabellen, erwartete Ergebnisse |

## Rollen

Die Anwendung entscheidet nichts fachlich. Der Fachbereich legt fest, welche Werte Basis sind; die Regeln wachsen
Beispiel für Beispiel (D24). Kreislauf:

1. Adresse und Team-Passwort an den Fachbereich geben; beim Anmelden trägt jede:r den eigenen Namen ein.
2. Material öffnen: Baum zeigt, welche Positionen in die Basis-Stückliste kommen und warum.
3. Regeln als **Entwurf** ändern (Basis/Offen/Nie Basis, Rang, Kürzel) – Baum rechnet sofort neu;
   „Auswirkung auf alle Materialien“ zeigt die Folgen. Entwurf bleibt je Name auf dem Server erhalten.
4. **Übernehmen** mit Begründung → historisiert (D21); Konflikt, wenn jemand dieselbe Regel inzwischen geändert hat.
5. Material bewerten (Richtig / Sollte raus / Sollte rein, fehlende Materialien ergänzen), speichern, bestätigen.
   Bestätigte Materialien sind Referenz für `basis-bom regress`.
6. `basis-bom run` / `export` → SAP-Format.
