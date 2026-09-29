# Deployment (Prototyp „Export konfigurierbare Stücklisten“)

Ein Host (Standard `dpn-svr-iot`), zwei Container je Umgebung, Datenbank im gemeinsamen Postgres-Container.

```
Browser ──> Host-nginx (https://iot.polipol-service.de/app/dpn/test/konfig-stueckliste-export/)
              └─> konfig_stueckliste_export_frontend_<env>  (nginx, Vue-App, /api → Backend)
                    └─> konfig_stueckliste_export_backend_<env>  (FastAPI + basis_bom, Port 8000)
                          ├─> postgres_db_dev|prod  Datenbank konfig_stueckliste_export[_test]
                          ├─ /data/exports  ← $DEPLOY_DIR/base/exports  (SAP-Exporte, nur lesend)
                          └─ /data/out      ← $DEPLOY_DIR/out            (FRAGEN.md, Header-Bericht)
```

## CI → CD

1. **GitLab CI** (`.gitlab-ci.yml`, `backend/`- und `frontend/build-image-pipeline.yml`): Semgrep/Trivy/Hadolint,
   `ruff` + `pytest` (Fachlogik und API gegen Postgres), `eslint` + `vue-tsc` + `vitest`, Playwright-E2E gegen
   Backend mit Beispieldaten. Auf dem Default-Branch: Images per buildah nach Harbor
   (`dap-api/konfig-stueckliste-export`, `dap-ui/konfig-stueckliste-export`, Tag = Commit-SHA), Cosign-Signatur.
   Build-Kontext ist das Repo-Wurzelverzeichnis (das Backend-Image enthält `basis_bom/`, `sql/`, `legacy/`, Fixtures).
2. **Jenkins** (`Jenkinsfile`): Parameter `TARGET_SERVER`, `ENVIRONMENT`, `IMAGE_TAG_*`, `RELOAD_EXPORTS`.
   Ablauf: Host prüfen → Images ziehen → Datenbank anlegen bzw. Schema `basis_bom` sichern (`pg_dump`, `~/backups`,
   letzte 20) → alte Container als `*-previous` parken → Backend starten (Health) → Frontend starten (Health +
   Durchstich `/api/health`) → optional Exporte neu laden → Aufräumen. Bei Fehler starten die alten Container wieder.

Das Jenkinsfile lässt sich ohne Jenkins prüfen (CI-Job `lint:jenkinsfile`): `groovy deploy/jenkinsfile-pruefen.groovy
Jenkinsfile test` rendert alle Remote-Befehle nach `build/jenkins-befehle-test.sh` und prüft sie mit `bash -n`.

Rollback: nur wenn die alten Container schon geparkt waren (Fehler bei Host-Prüfung, Images oder Datenbank lassen
die laufende Version unberührt), auch bei Abbruch/Timeout (`aborted`). Sobald das neue Frontend gesund ist, wird
nicht mehr zurückgerollt; ein Fehler beim Neuladen der Exporte macht den Build nur UNSTABLE.

## Einmalig auf dem Host

```bash
P=konfig-stueckliste-export; ENV=test        # bzw. prod
mkdir -p ~/deployment/${P}_${ENV}/base/exports ~/deployment/${P}_${ENV}/out
cp sens.env.example ~/deployment/${P}_${ENV}/base/sens.env   # Vorlage: deploy/sens.env.example
chmod 600 ~/deployment/${P}_${ENV}/base/sens.env              # SECRET_KEY, MASTER_PASSWORD_ADMIN, DB-Zugang eintragen
```

Eigene Datenbank-Rolle (einmalig je Postgres-Container; Name/Passwort wie in `sens.env`):

```bash
docker exec -it postgres_db_dev psql -U postgres -c "CREATE ROLE konfig_stueckliste_export LOGIN PASSWORD '…'"
```

Die Datenbank legt das Jenkinsfile beim ersten Deploy an (`createdb -O <Rolle>`); die App legt darin ihre Schemas
`sap_raw` und `basis_bom` selbst an.

**Host-nginx**: Pfad `/app/dpn/<env-pfad>` unverändert an den Frontend-Container weiterreichen (das Frontend
läuft mit `VITE_BASE_PATH=/app/dpn/test/konfig-stueckliste-export/` und leitet `…/api/` selbst ans Backend).
Der Host-nginx-Container muss im Netz `app_network` hängen und Docker-DNS (`resolver 127.0.0.11`) nutzen.

```nginx
location = /app/dpn/test/konfig-stueckliste-export { return 301 $scheme://$host$uri/; }
location /app/dpn/test/konfig-stueckliste-export/ {
    resolver 127.0.0.11 valid=30s;
    set $upstream konfig_stueckliste_export_frontend_test;
    proxy_pass http://$upstream:80;          # ohne URI-Teil → Pfad bleibt erhalten
    proxy_set_header Host localhost;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;   # „Auswirkung auf alle Materialien“ rechnet mit echten Daten länger
}
```

Ein eigener `…/api/`-Block direkt zum Backend (`rewrite … /api$1`, `proxy_pass http://$upstream:8000`) funktioniert
ebenfalls, ist aber nicht nötig; dann greift allerdings die Login-Drosselung des Frontend-nginx nicht.

## Exporte laden

Dateien laut `docs/EXPORTE.md` nach `$DEPLOY_DIR/base/exports/` kopieren. Dann eines von:

- Oberfläche → **Datenstand** → „Exporte neu laden“ (alle Nutzer sehen währenddessen „Daten werden geladen …“),
- Jenkins mit `RELOAD_EXPORTS=yes`,
- `docker exec konfig_stueckliste_export_backend_test python scripts/neu_laden.py --warten`.

Beim allerersten Start mit leerer Datenbank lädt das Backend vorhandene Exporte automatisch. Regeln, Bewertungen,
Bestätigungen und Entwürfe (Schema `basis_bom`) bleiben beim Neuladen erhalten. Prüfpunkte und Header-Bericht
landen in `$DEPLOY_DIR/out/`.

## Hängt / dauert lange?

- `docker logs -f konfig_stueckliste_export_backend_test`: jeder Ladeschritt mit Dauer („… – fertig nach 42.0 s“),
  am Ende „Datenstand: bereit nach … s“. Nach jedem Neustart werden die SAP-Daten aus der Datenbank gelesen und
  vorberechnet; bis dahin zeigt die Oberfläche „Daten werden geladen …“ mit den Schritten.
- `docker kill -s USR1 konfig_stueckliste_export_backend_test` schreibt die Stacks aller Threads ins Log
  (wo rechnet es gerade?), ohne den Container anzuhalten.
- `docker stats konfig_stueckliste_export_backend_test`: Speicher (STPO ~1 GB braucht entsprechend RAM).

## Wiederherstellen

```bash
docker exec -i postgres_db_dev pg_restore -U postgres -d konfig_stueckliste_export_test --clean --if-exists \
  < ~/backups/konfig_stueckliste_export_test_basis_bom_<zeitstempel>.dump
docker restart konfig_stueckliste_export_backend_test
```

## Lokal ausprobieren

- `docker compose up --build` → http://localhost:3000 (Passwort `test`, Beispieldaten).
- `deploy/lokal-deploy.sh` spielt die Jenkins-Schritte mit denselben `docker run`-Aufrufen nach, inkl. Host-nginx →
  http://localhost:8088/app/dpn/test/konfig-stueckliste-export/.
- E2E: `cd frontend && E2E_BASE_URL=http://localhost:8088/app/dpn/test/konfig-stueckliste-export npx playwright test`
  (wiederholbar; für frische Beispieldaten vorher `RESET=1 deploy/lokal-deploy.sh`).

Host-nginx: Die Login-Bremse im Frontend-nginx nimmt als Client-Adresse den letzten Eintrag in `X-Forwarded-For`
– der Host-nginx muss ihn mit `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` setzen (siehe oben).
